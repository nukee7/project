"""Entry point for: python -m company_agent

Three modes:
    python -m company_agent          → starts production API server
    python -m company_agent --test   → runs test examples with all stubs
    python -m company_agent --live   → runs with real OpenAI LLM + stub data
"""

import sys

if "--test" in sys.argv:
    import asyncio
    from test.company_agent.example_runner import main
    asyncio.run(main())
elif "--live" in sys.argv:
    import asyncio
    from test.company_agent.live_llm_runner import main
    asyncio.run(main())
else:
    from company_agent.main import main
    main()
