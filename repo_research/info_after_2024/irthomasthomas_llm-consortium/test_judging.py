import llm
from llm_consortium import create_consortium
import json
import os

# Set a dummy API key for 'testing' model if needed, though llm.get_model should handle it
os.environ["LLM_DUMMY_API_KEY"] = "dummy"

def run_test(judging_method):
    print(f"--- Running test for judging_method: '{judging_method}' ---")
    
    # Mock the models to return predictable responses with IDs
    # This requires a more complex setup than just using fake(), so we'll
    # use a simple approach of having the models return slightly different text.
    class MockModel(llm.Model):
        def __init__(self, model_id, response_text):
            self.model_id = model_id
            self.response_text = response_text
        
        def prompt_sync(self, prompt, **kwargs):
            return llm.Response.fake(self.response_text, self)

    # Register mock models
    llm.register_model("mock-model-1", MockModel("mock-model-1", "This is the first response."))
    llm.register_model("mock-model-2", MockModel("mock-model-2", "This is the second, and better, response."))
    
    # Mock the arbiter
    class MockArbiter(llm.Model):
        def __init__(self, model_id, method):
            self.model_id = model_id
            self.method = method

        def prompt_sync(self, prompt, **kwargs):
            if self.method == 'pick-one':
                # The arbiter should pick the second response as 'better'
                response_content = "<winner><response_id>2</response_id></winner>"
            elif self.method == 'rank':
                 # Rank the second one as best
                response_content = '<ranking><rank position="1">2</rank><rank position="2">1</rank></ranking>'
            else: # default synthesis
                response_content = "<synthesis>Synthesized response.</synthesis><confidence>0.9</confidence>"
            
            return llm.Response.fake(response_content, self)

    llm.register_model("mock-arbiter", MockArbiter("mock-arbiter", judging_method))

    consortium = create_consortium(
        models=["mock-model-1", "mock-model-2"],
        arbiter="mock-arbiter",
        judging_method=judging_method
    )

    prompt = "What is the best response?"
    result = consortium.orchestrate(prompt)

    print("Final Synthesis:", result.get("synthesis", {}).get("synthesis"))
    print("Analysis:", result.get("synthesis", {}).get("analysis"))
    
    if judging_method == 'pick-one':
        assert "second, and better" in result.get("synthesis", {}).get("synthesis")
        print("Pick-one test PASSED")
    elif judging_method == 'rank':
        assert "second, and better" in result.get("synthesis", {}).get("synthesis")
        print("Rank test PASSED")
    
    print("-" * 20 + "\n")


if __name__ == "__main__":
    run_test("pick-one")
    run_test("rank")

