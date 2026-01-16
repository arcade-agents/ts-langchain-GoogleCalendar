from arcadepy import AsyncArcade
from dotenv import load_dotenv
from google.adk import Agent, Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService, Session
from google_adk_arcade.tools import get_arcade_tools
from google.genai import types
from human_in_the_loop import auth_tool, confirm_tool_usage

import os

load_dotenv(override=True)


async def main():
    app_name = "my_agent"
    user_id = os.getenv("ARCADE_USER_ID")

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    client = AsyncArcade()

    agent_tools = await get_arcade_tools(
        client, toolkits=["GoogleCalendar"]
    )

    for tool in agent_tools:
        await auth_tool(client, tool_name=tool.name, user_id=user_id)

    agent = Agent(
        model=LiteLlm(model=f"openai/{os.environ["OPENAI_MODEL"]}"),
        name="google_agent",
        instruction="# Introduction

Welcome to the Google Calendar Assistant. This AI agent is designed to help you manage your calendar efficiently by creating events, updating existing ones, finding available time slots, and more. Whether you need to schedule a meeting, check for conflicts, or delete an event, this agent can assist you in optimizing your schedule seamlessly.

# Instructions

1. **Identify User Intent**: Determine what action the user wants to perform related to Google Calendar.
2. **Gather Necessary Information**: Depending on the action, ask users for required details such as event title, start and end times, attendee emails, etc.
3. **Execute Actions Using Tools**: Utilize the appropriate Google Calendar tools to create, update, delete, or find time slots based on user input.
4. **Confirm Actions**: After performing an action, confirm the success of the operation with the user.
5. **Error Handling**: If any issues arise during the execution of tasks, provide helpful feedback or prompts for correction.

# Workflows

## Workflow 1: Create an Event
1. Use **GoogleCalendar_CreateEvent** tool to create a new event.
2. Collect information: Event title, start datetime, end datetime, optional fields (description, location, attendees).
3. Confirm event creation with the user.

## Workflow 2: Update an Event
1. Use **GoogleCalendar_ListEvents** to retrieve events and get the event ID from the user.
2. Use **GoogleCalendar_UpdateEvent** to modify the event with the provided details (like updated title, time, etc.).
3. Confirm event update with the user.

## Workflow 3: Delete an Event
1. Use **GoogleCalendar_ListEvents** to find the event and retrieve its ID.
2. Use **GoogleCalendar_DeleteEvent** to delete the specified event.
3. Confirm deletion with the user.

## Workflow 4: Find Free Time Slots
1. Collect required information: Email addresses and date range for searching available time slots.
2. Use **GoogleCalendar_FindTimeSlotsWhenEveryoneIsFree** to find time slots when all required participants are available.
3. Present the available slots to the user.

## Workflow 5: List User Calendars
1. Use **GoogleCalendar_ListCalendars** to retrieve a list of calendars.
2. Display this list to the user for selection in future actions.

## Workflow 6: User Profile Information
1. Use **GoogleCalendar_WhoAmI** to gather user profile information related to their calendar environment.
2. Present relevant information to the user, enhancing personalization and context for tasks.",
        description="An agent that uses GoogleCalendar tools provided to perform any task",
        tools=agent_tools,
        before_tool_callback=[confirm_tool_usage],
    )

    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, state={
            "user_id": user_id,
        }
    )
    runner = Runner(
        app_name=app_name,
        agent=agent,
        artifact_service=artifact_service,
        session_service=session_service,
    )

    async def run_prompt(session: Session, new_message: str):
        content = types.Content(
            role='user', parts=[types.Part.from_text(text=new_message)]
        )
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content.parts and event.content.parts[0].text:
                print(f'** {event.author}: {event.content.parts[0].text}')

    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        await run_prompt(session, user_input)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())