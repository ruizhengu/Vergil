This is a branch for developing the neuro symbolic reasoning approach for the smart contract project, the result should be reflected on the frontend as well.

Basic logic:
natural language contract content -> LLM -> symbolic representation 1
user requirements -> LLM -> symbolic representation 2
try to match them through logic verifier -> yes -> output (both contract and 'requirements met' UI) 
                  -> no -> go to refinement loop branch -> refine the contract until meet all requirements (show user the refining process as well? )


已实现交易执行前双层验证：Layer 2（Pydantic Guardrail）+ Layer 3（SMT with Z3），失败即硬拦截，不执行链上操作。
新增金融动作模型与结构化错误：在 agent_responses.py 增加 FinancialAction、StructuredValidationError、SMTState。
新增验证模块：在 guardrails.py 做参数校验，在 smt_logic.py 做“LLM提取约束 + 合约事实提取 + Z3求解”。
已接入三条关键路径：
聊天准备交易：chat.py
审批提交前：approval.py
广播交易前：transactions.py
依赖已补充：在 pyproject.toml 添加 z3-solver。