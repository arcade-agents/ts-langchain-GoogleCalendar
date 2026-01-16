from agents import (Agent, Runner, AgentHooks, Tool, RunContextWrapper,
                    TResponseInputItem,)
from functools import partial
from arcadepy import AsyncArcade
from agents_arcade import get_arcade_tools
from typing import Any
from human_in_the_loop import (UserDeniedToolCall,
                               confirm_tool_usage,
                               auth_tool)

import globals


class CustomAgentHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.event_counter = 0
        self.display_name = display_name

    async def on_start(self,
                       context: RunContextWrapper,
                       agent: Agent) -> None:
        self.event_counter += 1
        print(f"### ({self.display_name}) {
              self.event_counter}: Agent {agent.name} started")

    async def on_end(self,
                     context: RunContextWrapper,
                     agent: Agent,
                     output: Any) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended with output {output}"
                agent.name} ended"
        )

    async def on_handoff(self,
                         context: RunContextWrapper,
                         agent: Agent,
                         source: Agent) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                source.name} handed off to {agent.name}"
        )

    async def on_tool_start(self,
                            context: RunContextWrapper,
                            agent: Agent,
                            tool: Tool) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}:"
            f" Agent {agent.name} started tool {tool.name}"
            f" with context: {context.context}"
        )

    async def on_tool_end(self,
                          context: RunContextWrapper,
                          agent: Agent,
                          tool: Tool,
                          result: str) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended tool {tool.name} with result {result}"
                agent.name} ended tool {tool.name}"
        )


async def main():

    context = {
        "user_id": os.getenv("ARCADE_USER_ID"),
    }

    client = AsyncArcade()

    arcade_tools = await get_arcade_tools(
        client, toolkits=["GoogleCalendar"]
    )

    for tool in arcade_tools:
        # - human in the loop
        if tool.name in ENFORCE_HUMAN_CONFIRMATION:
            tool.on_invoke_tool = partial(
                confirm_tool_usage,
                tool_name=tool.name,
                callback=tool.on_invoke_tool,
            )
        # - auth
        await auth_tool(client, tool.name, user_id=context["user_id"])

    agent = Agent(
        name="",
        instructions="# Introduction

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
        model=os.environ["OPENAI_MODEL"],
        tools=arcade_tools,
        hooks=CustomAgentHooks(display_name="")
    )

    # initialize the conversation
    history: list[TResponseInputItem] = []
    # run the loop!
    while True:
        prompt = input("You: ")
        if prompt.lower() == "exit":
            break
        history.append({"role": "user", "content": prompt})
        try:
            result = await Runner.run(
                starting_agent=agent,
                input=history,
                context=context
            )
            history = result.to_input_list()
            print(result.final_output)
        except UserDeniedToolCall as e:
            history.extend([
                {"role": "assistant",
                 "content": f"Please confirm the call to {e.tool_name}"},
                {"role": "user",
                 "content": "I changed my mind, please don't do it!"},
                {"role": "assistant",
                 "content": f"Sure, I cancelled the call to {e.tool_name}."
                 " What else can I do for you today?"
                 },
            ])
            print(history[-1]["content"])

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())