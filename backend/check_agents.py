from app.database import SessionLocal
from app.models.ai_agent import AIAgent

db = SessionLocal()

print("=== YOUR AI AGENTS ===\n")

agents = db.query(AIAgent).all()

if not agents:
    print("No AI agents found")
else:
    for i, agent in enumerate(agents, 1):
        print(f"Agent #{i}")
        print(f"  Name: {agent.name}")
        print(f"  User ID: {agent.user_id}")
        if hasattr(agent, 'retell_agent_id'):
            print(f"  Retell Agent: {agent.retell_agent_id}")
        print(f"\n  System Prompt:")
        print(f"  {agent.system_prompt if agent.system_prompt else 'None'}")
        print(f"\n  Greeting:")
        print(f"  {agent.greeting_message if agent.greeting_message else 'None'}")
        print("\n" + "-"*50 + "\n")

db.close()
