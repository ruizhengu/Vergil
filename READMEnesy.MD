This is a branch for developing the neuro symbolic reasoning approach for the smart contract project, the result should be reflected on the frontend as well.

Basic logic:
natural language contract content -> LLM -> symbolic representation 1
user requirements -> LLM -> symbolic representation 2
try to match them through logic verifier -> yes -> output (both contract and 'requirements met' UI) 
                  -> no -> go to refinement loop branch -> refine the contract until meet all requirements (show user the refining process as well? )