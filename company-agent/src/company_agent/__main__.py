"""Entry point for: python -m company_agent

Routes to the correct runner based on --test flag:
    python -m company_agent          → starts production API server
    python -m company_agent --test   → runs test examples with stubs
"""

import sys

if "--test" in sys.argv:
    import asyncio
    from company_agent.testing.example_runner import main
    asyncio.run(main())
else:
    from company_agent.main import main
    main()
