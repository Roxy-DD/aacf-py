import os
import sys

# Ensure the parent directory is in sys.path so 'aacf' can be imported when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from pydantic import BaseModel

from aacf import AACF, LLMConfig

app = AACF(__name__, config=LLMConfig(url="http://127.0.0.1:8080/v1/chat/completions", model="qwen2.5-7b-instruct"))


class Person(BaseModel):
    name: str
    age: int
    occupation: str


@app.node("extract_person").what("Extract person info from text")
def extract_person(text: str) -> Person:
    """
     【AACF 智能节点 / Smart Node】:
    🎯 核心任务 / Core Task: Extract person info from text
     环境 / Environment:
    📦 返回格式 / Return Format: Strict JSON matching Person
    """
    # type: ignore
    ...


@app.node("analyzer").what("Analyze the person")
def analyzer(extract_person: Person):
    """
     【AACF 智能节点 / Smart Node】:
    🎯 核心任务 / Core Task: Analyze the person
     环境 / Environment:
    """
    # This is a pure python node to verify we received a Person object
    print(f"Received strongly typed Person object: {type(extract_person)}")
    print(f"Name: {extract_person.name}, Age: {extract_person.age}")
    return {"status": "success", "analyzed_name": extract_person.name}


if __name__ == "__main__":
    import unittest
    from unittest.mock import patch

    class TestPydanticIntegration(unittest.TestCase):
        @patch("aacf.core.llm_call")
        def test_validation_retry_and_success(self, mock_llm_call):
            # First attempt: Return invalid JSON (missing age)
            # Second attempt: Return valid JSON
            mock_llm_call.side_effect = [
                '{"name": "Alice", "occupation": "Engineer"}',  # Attempt 1
                '{"name": "Alice", "age": 30, "occupation": "Engineer"}',  # Attempt 2
            ]

            try:
                result = app.run_pipeline(inputs={"extract_person": {"text": "Alice is a 30 year old engineer."}})
                print("PIPELINE RESULT:", result)
            except Exception as e:
                print("PIPELINE ERROR:", e)
                raise

            self.assertEqual(mock_llm_call.call_count, 2)

            # Verify the second call's prompt contains the validation error
            second_call_kwargs = mock_llm_call.call_args_list[1][1]
            self.assertIn("failed schema validation", second_call_kwargs["user_prompt"])
            self.assertIn("Field required", second_call_kwargs["user_prompt"])

            # Verify the final result passed through the pure python node successfully
            self.assertEqual(result["analyzer"]["status"], "success")
            self.assertEqual(result["analyzer"]["analyzed_name"], "Alice")

            print("Pydantic integration test passed successfully!")

    unittest.main()
