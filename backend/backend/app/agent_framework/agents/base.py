"""
Base Agent Class
All specialist agents inherit from this
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_openai_functions_agent
from app.agent_framework.core.state import AgentState
from app.agent_framework.core.config import AgentConfig


class BaseAgent(ABC):
    """Base class for all specialist agents"""
    
    def __init__(
        self,
        name: str,
        role: str,
        config: AgentConfig,
        tools: list = None
    ):
        self.name = name
        self.role = role
        self.config = config
        self.tools = tools or []
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout
        )
        
        # Create agent prompt
        self.system_prompt = self._get_system_prompt()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # Create agent executor if tools are provided
        if self.tools:
            agent = create_openai_functions_agent(
                llm=self.llm,
                tools=self.tools,
                prompt=self.prompt
            )
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                verbose=True,
                max_iterations=5
            )
        else:
            self.agent_executor = None
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Get the system prompt for this agent"""
        pass
    
    @abstractmethod
    async def process(self, state: AgentState) -> Dict[str, Any]:
        """Process a task with this agent"""
        pass
    
    async def execute(self, input_text: str, chat_history: list = None) -> str:
        """Execute agent with input"""
        if self.agent_executor:
            result = await self.agent_executor.ainvoke({
                "input": input_text,
                "chat_history": chat_history or []
            })
            return result.get("output", "")
        else:
            # Simple LLM call without tools
            messages = [
                ("system", self.system_prompt),
                ("human", input_text)
            ]
            response = await self.llm.ainvoke(messages)
            return response.content
    
    def add_tool(self, tool):
        """Add a tool to this agent"""
        self.tools.append(tool)
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name}, role={self.role})"
