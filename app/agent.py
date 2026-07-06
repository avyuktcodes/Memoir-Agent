# ruff: noqa
import os
import re
import sys
import google.auth
import json
from pydantic import BaseModel, Field
from google.adk.agents import Agent
from google.adk.plugins.bigquery_agent_analytics_plugin import BigQueryAgentAnalyticsPlugin
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools import google_search
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

try:
    _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
except Exception:
    pass

mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["/Users/avyukt/Desktop/memoir-agent/mcp_server/server.py"],
        ),
    )
)

async def generate_memories_callback(callback_context: CallbackContext):
    """Sends the session's events to Memory Bank for memory generation."""
    await callback_context.add_session_to_memory()
    return None

def save_biography_chapter(content: str) -> str:
    """Saves the synthesized biography chapter after redacting sensitive information.
    
    Args:
        content: The text of the biography chapter.
    """
    # Redact SSN-like patterns (XXX-XX-XXXX)
    redacted = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED SSN]', content)
    
    # Redact phone numbers (XXX-XXX-XXXX)
    redacted = re.sub(r'\b\d{3}-\d{3}-\d{4}\b', '[REDACTED PHONE]', redacted)
    
    # Save to a local file
    os.makedirs("/Users/avyukt/Desktop/memoir-agent/mock_data/output", exist_ok=True)
    with open("/Users/avyukt/Desktop/memoir-agent/mock_data/output/memoir.md", "a") as f:
        f.write(redacted + "\n\n")
        
    return f"Chapter saved securely with sensitive data redacted. Preview:\n{redacted[:200]}..."

def fetch_family_prompts() -> str:
    """Fetches questions or prompts submitted by the user's family members."""
    return "Grandson Jimmy wants to know: 'What was your first car and how did you buy it?'"

class PublisherOutput(BaseModel):
    title: str = Field(description="The title of the biography chapter.")
    year_or_era: str = Field(description="The historical year or era the chapter focuses on.")
    narrative_text: str = Field(description="The beautifully written, fact-checked chapter text.")
    photos_referenced: list[str] = Field(description="List of photo filenames referenced in the chapter.")

async def save_structured_output_callback(callback_context: CallbackContext) -> None:
    # Save the structured output to disk
    output = callback_context.state.get("publisher_result")
    if output:
        os.makedirs("/Users/avyukt/Desktop/memoir-agent/mock_data/output", exist_ok=True)
        with open("/Users/avyukt/Desktop/memoir-agent/mock_data/output/memoir_structured.json", "w") as f:
            f.write(json.dumps(output, indent=2))

a2ui_manager = A2uiSchemaManager("0.9.1", catalogs=[BasicCatalog().get_config("0.9.1")])
a2ui_instruction = a2ui_manager.generate_system_prompt(role_description="You are a digital legacy architect that uses interactive UI components to display information.")
a2ui_instruction_escaped = a2ui_instruction.replace("{", "{{").replace("}", "}}")

interviewer_agent = Agent(
    name="interviewer",
    model=Gemini(model="gemini-flash-latest"),
    description="Responsible for asking the user nostalgic questions about their life to gather stories.",
    instruction=f"""You are a warm, empathetic biographer. Your job is to interview the user about their life.
    Ask one question at a time. Be engaging and encourage them to share details.
    Whenever appropriate, encourage the user to click the microphone icon and record voice notes instead of typing!
    Use the fetch_family_prompts tool to see if family members have requested any specific questions.
    Once you have enough information for a chapter, pass the conversation back to the coordinator.
    
    {a2ui_instruction_escaped}
    """,
    tools=[fetch_family_prompts],
)

synthesizer_agent = Agent(
    name="synthesizer",
    model=Gemini(model="gemini-flash-latest"),
    description="Synthesizes gathered stories and photos into a final biography chapter.",
    instruction=f"""You are a skilled writer. Take the stories gathered from the user and write a beautifully 
    formatted Markdown biography chapter. Use the MCP tools to list and read any historical photos 
    the user mentions or that are available, and incorporate their descriptions into the narrative.
    
    {a2ui_instruction_escaped}
    """,
    tools=[mcp_toolset],
)

fact_checker_agent = Agent(
    name="fact_checker",
    model=Gemini(model="gemini-flash-latest"),
    description="Fact-checks historical dates and facts in the biography.",
    instruction=f"""You are a meticulous fact-checker. Take the draft biography chapter and use the google_search tool to verify historical dates and facts mentioned (e.g., release year of a vintage car). Gently correct the timeline in footnotes if necessary.
    When you are done checking, ALWAYS use the `save_biography_chapter` tool to securely save it.
    
    {a2ui_instruction_escaped}
    """,
    tools=[google_search, save_biography_chapter],
)

publisher_agent = Agent(
    name="publisher",
    model=Gemini(model="gemini-flash-latest"),
    description="Formats the final, fact-checked biography chapter into a structured JSON format.",
    instruction="Take the fact-checked biography chapter and output it strictly according to the schema.",
    output_schema=PublisherOutput,
    output_key="publisher_result",
    after_agent_callback=save_structured_output_callback,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(model="gemini-flash-latest"),
    instruction="""You are the Memoir Coordinator. 
    1. First, delegate to the `interviewer` to gather stories from the user.
    2. Then, delegate to the `synthesizer` to fetch their photos and write the biography chapter draft.
    3. Then, delegate to the `fact_checker` to verify historical facts and save the raw markdown.
    4. Finally, delegate to the `publisher` to format the verified chapter into structured JSON.
    """,
    sub_agents=[interviewer_agent, synthesizer_agent, fact_checker_agent, publisher_agent],
    tools=[PreloadMemoryTool()],
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
    plugins=[BigQueryAgentAnalyticsPlugin(project_id=os.environ.get("GOOGLE_CLOUD_PROJECT", "mock-project"), dataset_id="memoir_analytics")]
)
