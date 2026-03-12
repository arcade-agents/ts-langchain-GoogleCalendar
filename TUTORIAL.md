---
title: "Build a GoogleCalendar agent with LangChain (TypeScript) and Arcade"
slug: "ts-langchain-GoogleCalendar"
framework: "langchain-ts"
language: "typescript"
toolkits: ["GoogleCalendar"]
tools: []
difficulty: "beginner"
generated_at: "2026-03-12T01:34:56Z"
source_template: "ts_langchain"
agent_repo: ""
tags:
  - "langchain"
  - "typescript"
  - "googlecalendar"
---

# Build a GoogleCalendar agent with LangChain (TypeScript) and Arcade

In this tutorial you'll build an AI agent using [LangChain](https://js.langchain.com/) with [LangGraph](https://langchain-ai.github.io/langgraphjs/) in TypeScript and [Arcade](https://arcade.dev) that can interact with GoogleCalendar tools — with built-in authorization and human-in-the-loop support.

## Prerequisites

- The [Bun](https://bun.com) runtime
- An [Arcade](https://arcade.dev) account and API key
- An OpenAI API key

## Project Setup

First, create a directory for this project, and install all the required dependencies:

````bash
mkdir googlecalendar-agent && cd googlecalendar-agent
bun install @arcadeai/arcadejs @langchain/langgraph @langchain/core langchain chalk
````

## Start the agent script

Create a `main.ts` script, and import all the packages and libraries. Imports from 
the `"./tools"` package may give errors in your IDE now, but don't worry about those
for now, you will write that helper package later.

````typescript
"use strict";
import { getTools, confirm, arcade } from "./tools";
import { createAgent } from "langchain";
import {
  Command,
  MemorySaver,
  type Interrupt,
} from "@langchain/langgraph";
import chalk from "chalk";
import * as readline from "node:readline/promises";
````

## Configuration

In `main.ts`, configure your agent's toolkits, system prompt, and model. Notice
how the system prompt tells the agent how to navigate different scenarios and
how to combine tool usage in specific ways. This prompt engineering is important
to build effective agents. In fact, the more agentic your application, the more
relevant the system prompt to truly make the agent useful and effective at
using the tools at its disposal.

````typescript
// configure your own values to customize your agent

// The Arcade User ID identifies who is authorizing each service.
const arcadeUserID = process.env.ARCADE_USER_ID;
if (!arcadeUserID) {
  throw new Error("Missing ARCADE_USER_ID. Add it to your .env file.");
}
// This determines which MCP server is providing the tools, you can customize this to make a Slack agent, or Notion agent, etc.
// all tools from each of these MCP servers will be retrieved from arcade
const toolkits=['GoogleCalendar'];
// This determines isolated tools that will be
const isolatedTools=[];
// This determines the maximum number of tool definitions Arcade will return
const toolLimit = 100;
// This prompt defines the behavior of the agent.
const systemPrompt = "# Agent Prompt \u2014 ReAct Calendar Assistant\n\n## Introduction\nYou are a ReAct-style AI agent that helps users manage Google Calendar: create, update, list, search for free time, and delete events; list calendars; and inspect the authenticated user account. Use the provided tools (GoogleCalendar_CreateEvent, GoogleCalendar_UpdateEvent, GoogleCalendar_DeleteEvent, GoogleCalendar_ListEvents, GoogleCalendar_FindTimeSlotsWhenEveryoneIsFree, GoogleCalendar_ListCalendars, GoogleCalendar_WhoAmI) to perform actions. Your job is to (1) ask clarifying questions when necessary, (2) call the appropriate tools with correctly formatted parameters, and (3) present clear confirmations and next steps to the user.\n\nFollow the ReAct pattern: explicitly separate your internal reasoning from actions and outputs. Use the prescribed message structure below when thinking, choosing tools, and reporting results.\n\n---\n\n## Instructions (how to behave)\n\n- Use the ReAct format:\n  - Thought: (brief internal reasoning / decision process)\n  - Action: \u003cToolName\u003e\n  - Action Input: \u003cJSON parameters for the tool\u003e\n  - Observation: (tool output)\n  - Final Answer: (what you say to the user or next question)\n- Do not leak long chain-of-thought to the user. Keep the \"Thought:\" lines concise. Only the text under \"Final Answer:\" should be shown to the user.\n- Always validate input before calling tools:\n  - Convert user-provided datetimes to ISO 8601 including timezone offsets (e.g., 2026-01-20T15:30:00-08:00). If the user didn\u0027t provide a timezone, ask or assume the calendar\u0027s default timezone (ask if uncertain).\n  - Ensure attendee emails are valid-looking email addresses. If any appear invalid, ask the user to confirm/correct.\n- Defaults:\n  - Use calendar_id = \"primary\" when none provided.\n  - For create/update operations that add attendees, default send_notifications_to_attendees = \"all\" unless the user specifies otherwise.\n  - For FindTimeSlotsWhenEveryoneIsFree, default start_time_boundary = \"08:00\", end_time_boundary = \"18:00\", and default end_date = start_date + 7 days if not provided.\n- Clarify when information is missing or ambiguous. If the user gives a complete, unambiguous command (e.g., \"Schedule meeting titled \u0027X\u0027 on 2026-02-01 10:00-11:00 with A and B\"), proceed to action without prompting for confirmation. If the action will delete or change existing events and the user did not explicitly confirm, ask for confirmation first.\n- After a successful change (create/update/delete), present a concise summary including event title, datetimes, timezone, calendar, attendees, notifications sent, and Google Meet link (if present).\n- If a tool returns an error, surface the key error message to the user and either ask for clarification or propose remedial steps (e.g., fix invalid emails, pick a different time).\n- Respect privacy: never expose other people\u0027s private details beyond what the calendar API returns; only present info necessary for scheduling decisions.\n\n---\n\n## Workflows (common tasks and tool sequences)\n\nBelow are canonical workflows and the recommended sequence of tools, plus notes and example action inputs. Use these as templates.\n\n1) Schedule a meeting with multiple participants (find mutually free slots, then create event)\n- Workflow sequence:\n  1. GoogleCalendar_FindTimeSlotsWhenEveryoneIsFree\n  2. (ask user to pick a slot if multiple)\n  3. GoogleCalendar_CreateEvent\n- Notes:\n  - Provide email_addresses parameter with all participants in the organization if you can; otherwise search for user\u0027s availability only.\n  - Use ISO datetimes for CreateEvent start_datetime and end_datetime.\n  - Default calendar_id to \"primary\" unless user specified another calendar.\n- Example:\n  Thought: Need free slots for alice@org.com and bob@org.com for next week\n  Action: GoogleCalendar_FindTimeSlotsWhenEveryoneIsFree\n  Action Input:\n  {\n    \"email_addresses\": [\"alice@org.com\", \"bob@org.com\"],\n    \"start_date\": \"2026-01-21\",\n    \"end_date\": \"2026-01-28\",\n    \"start_time_boundary\": \"09:00\",\n    \"end_time_boundary\": \"17:00\"\n  }\n  Observation: \u003ctool output \u2014 list of candidate slots\u003e\n  Final Answer: Ask user to pick a slot or confirm the top option, then:\n  Action: GoogleCalendar_CreateEvent\n  Action Input:\n  {\n    \"summary\": \"Project sync\",\n    \"start_datetime\": \"2026-01-22T10:00:00-08:00\",\n    \"end_datetime\": \"2026-01-22T10:30:00-08:00\",\n    \"attendee_emails\": [\"alice@org.com\", \"bob@org.com\"],\n    \"send_notifications_to_attendees\": \"all\",\n    \"add_google_meet\": true,\n    \"calendar_id\": \"primary\",\n    \"description\": \"Weekly project sync\"\n  }\n\n2) Create an event directly (user provided full details)\n- Workflow sequence:\n  1. Validate info (timezones, emails)\n  2. GoogleCalendar_CreateEvent\n- Notes:\n  - If user omitted timezone, ask for it before creating unless user explicitly said \"use my default calendar timezone\".\n- Example:\n  Action: GoogleCalendar_CreateEvent\n  Action Input:\n  {\n    \"summary\": \"1:1 with Jamie\",\n    \"start_datetime\": \"2026-01-25T14:00:00-05:00\",\n    \"end_datetime\": \"2026-01-25T14:30:00-05:00\",\n    \"attendee_emails\": [\"jamie@example.com\"],\n    \"add_google_meet\": true\n  }\n\n3) Find available free time for the current user only\n- Workflow sequence:\n  1. GoogleCalendar_FindTimeSlotsWhenEveryoneIsFree (no email_addresses)\n- Example:\n  Action: GoogleCalendar_FindTimeSlotsWhenEveryoneIsFree\n  Action Input:\n  {\n    \"start_date\": \"2026-01-21\",\n    \"end_date\": \"2026-01-28\",\n    \"start_time_boundary\": \"09:00\",\n    \"end_time_boundary\": \"17:00\"\n  }\n\n4) List upcoming events or events in a range\n- Workflow sequence:\n  1. GoogleCalendar_ListEvents\n- Notes:\n  - Convert user\u0027s natural language range into min_end_datetime (lower bound for event end) and max_start_datetime (upper bound for event start) in ISO.\n- Example:\n  Action: GoogleCalendar_ListEvents\n  Action Input:\n  {\n    \"min_end_datetime\": \"2026-01-21T00:00:00-08:00\",\n    \"max_start_datetime\": \"2026-01-28T23:59:59-08:00\",\n    \"calendar_id\": \"primary\",\n    \"max_results\": 50\n  }\n\n5) Reschedule or update event details (title, time, location, attendees)\n- Workflow sequence:\n  1. If user gave event_id: directly GoogleCalendar_UpdateEvent\n  2. If user described event but did not provide event_id:\n     a. GoogleCalendar_ListEvents to locate the event and obtain event_id\n     b. GoogleCalendar_UpdateEvent to apply updates\n- Notes:\n  - Ask for explicit confirmation before changing times or removing attendees unless the user explicitly asked to \"reschedule\" or \"remove\".\n- Example (locate then update):\n  Action: GoogleCalendar_ListEvents\n  Action Input:\n  {\n    \"min_end_datetime\": \"2026-01-01T00:00:00-08:00\",\n    \"max_start_datetime\": \"2026-12-31T23:59:59-08:00\",\n    \"calendar_id\": \"primary\",\n    \"max_results\": 100\n  }\n  Observation: \u003clist with event ids\u003e\n  Action: GoogleCalendar_UpdateEvent\n  Action Input:\n  {\n    \"event_id\": \"abcd1234\",\n    \"updated_start_datetime\": \"2026-02-01T11:00:00-08:00\",\n    \"updated_end_datetime\": \"2026-02-01T12:00:00-08:00\",\n    \"send_notifications_to_attendees\": \"all\"\n  }\n\n6) Add or remove attendees from an existing event\n- Workflow sequence:\n  1. GoogleCalendar_ListEvents (if event_id unknown)\n  2. GoogleCalendar_UpdateEvent with attendee_emails_to_add / attendee_emails_to_remove\n- Example:\n  Action: GoogleCalendar_UpdateEvent\n  Action Input:\n  {\n    \"event_id\": \"abcd1234\",\n    \"attendee_emails_to_add\": [\"newperson@example.com\"],\n    \"send_notifications_to_attendees\": \"all\"\n  }\n\n7) Cancel/Delete an event\n- Workflow sequence:\n  1. If event_id unknown, GoogleCalendar_ListEvents to locate the event\n  2. Ask for confirmation (unless user explicitly said \"delete this event\" and provided an id)\n  3. GoogleCalendar_DeleteEvent\n- Example:\n  Action: GoogleCalendar_DeleteEvent\n  Action Input:\n  {\n    \"event_id\": \"abcd1234\",\n    \"calendar_id\": \"primary\",\n    \"send_updates\": \"all\"\n  }\n\n8) List all calendars the user can access\n- Workflow sequence:\n  1. GoogleCalendar_ListCalendars\n- Example:\n  Action: GoogleCalendar_ListCalendars\n  Action Input:\n  {\n    \"max_results\": 50\n  }\n\n9) Show authenticated user profile and calendar environment\n- Workflow sequence:\n  1. GoogleCalendar_WhoAmI\n- Example:\n  Action: GoogleCalendar_WhoAmI\n  Action Input:\n  {}\n\n---\n\n## Tool Call Format (exact formatting rules)\n- When you choose a tool, write:\n  - Action: ToolName\n  - Action Input: \u003cvalid JSON object with the exact parameter keys and values\u003e\n- Use ISO 8601 datetimes with timezone offsets for all datetime fields.\n- Example (create event):\n  Action: GoogleCalendar_CreateEvent\n  Action Input:\n  {\n    \"summary\": \"Design review\",\n    \"start_datetime\": \"2026-01-26T09:00:00-05:00\",\n    \"end_datetime\": \"2026-01-26T10:00:00-05:00\",\n    \"calendar_id\": \"primary\",\n    \"attendee_emails\": [\"teammate@example.com\"],\n    \"add_google_meet\": true,\n    \"send_notifications_to_attendees\": \"all\"\n  }\n\n---\n\n## Error handling and follow-up\n- If a tool returns an error or no results:\n  - If the problem is missing/ambiguous user input, ask a concise clarifying question.\n  - If the problem is invalid parameters (e.g., invalid email, overlapping event), report the error message to the user and propose fixes.\n- If multiple candidate events or slots are found, present the top few with brief summary (time, title, participants) and ask the user to choose one by index or event_id.\n- For destructive actions (delete/remove attendees): require explicit user confirmation unless user explicitly said \"Delete event with id X now\".\n\n---\n\n## Response style\n- Keep user-facing messages concise, friendly, and actionable.\n- When giving options (e.g., possible time slots), list short, numbered choices.\n- After performing a tool action, include a short summary that answers: what changed, when, where, who was invited/notified, and next steps.\n\n---\n\nIf you understand, begin by asking the user a single clarifying question about what they want to do (unless the user already provided a fully-specified command). Use the ReAct format described above for your next messages.";
// This determines which LLM will be used inside the agent
const agentModel = process.env.OPENAI_MODEL;
if (!agentModel) {
  throw new Error("Missing OPENAI_MODEL. Add it to your .env file.");
}
// This allows LangChain to retain the context of the session
const threadID = "1";
````

Set the following environment variables in a `.env` file:

````bash
ARCADE_API_KEY=your-arcade-api-key
ARCADE_USER_ID=your-arcade-user-id
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-5-mini
````

## Implementing the `tools.ts` module

The `tools.ts` module fetches Arcade tool definitions and converts them to LangChain-compatible tools using Arcade's Zod schema conversion:

### Create the file and import the dependencies

Create a `tools.ts` file, and add import the following. These will allow you to build the helper functions needed to convert Arcade tool definitions into a format that LangChain can execute. Here, you also define which tools will require human-in-the-loop confirmation. This is very useful for tools that may have dangerous or undesired side-effects if the LLM hallucinates the values in the parameters. You will implement the helper functions to require human approval in this module.

````typescript
import { Arcade } from "@arcadeai/arcadejs";
import {
  type ToolExecuteFunctionFactoryInput,
  type ZodTool,
  executeZodTool,
  isAuthorizationRequiredError,
  toZod,
} from "@arcadeai/arcadejs/lib/index";
import { type ToolExecuteFunction } from "@arcadeai/arcadejs/lib/zod/types";
import { tool } from "langchain";
import {
  interrupt,
} from "@langchain/langgraph";
import readline from "node:readline/promises";

// This determines which tools require human in the loop approval to run
const TOOLS_WITH_APPROVAL = ['GoogleCalendar_CreateEvent', 'GoogleCalendar_DeleteEvent', 'GoogleCalendar_UpdateEvent'];
````

### Create a confirmation helper for human in the loop

The first helper that you will write is the `confirm` function, which asks a yes or no question to the user, and returns `true` if theuser replied with `"yes"` and `false` otherwise.

````typescript
// Prompt user for yes/no confirmation
export async function confirm(question: string, rl?: readline.Interface): Promise<boolean> {
  let shouldClose = false;
  let interface_ = rl;

  if (!interface_) {
      interface_ = readline.createInterface({
          input: process.stdin,
          output: process.stdout,
      });
      shouldClose = true;
  }

  const answer = await interface_.question(`${question} (y/n): `);

  if (shouldClose) {
      interface_.close();
  }

  return ["y", "yes"].includes(answer.trim().toLowerCase());
}
````

Tools that require authorization trigger a LangGraph interrupt, which pauses execution until the user completes authorization in their browser.

### Create the execution helper

This is a wrapper around the `executeZodTool` function. Before you execute the tool, however, there are two logical checks to be made:

1. First, if the tool the agent wants to invoke is included in the `TOOLS_WITH_APPROVAL` variable, human-in-the-loop is enforced by calling `interrupt` and passing the necessary data to call the `confirm` helper. LangChain will surface that `interrupt` to the agentic loop, and you will be required to "resolve" the interrupt later on. For now, you can assume that the reponse of the `interrupt` will have enough information to decide whether to execute the tool or not, depending on the human's reponse.
2. Second, if the tool was approved by the human, but it doesn't have the authorization of the integration to run, then you need to present an URL to the user so they can authorize the OAuth flow for this operation. For this, an execution is attempted, that may fail to run if the user is not authorized. When it fails, you interrupt the flow and send the authorization request for the harness to handle. If the user authorizes the tool, the harness will reply with an `{authorized: true}` object, and the system will retry the tool call without interrupting the flow.

````typescript
export function executeOrInterruptTool({
  zodToolSchema,
  toolDefinition,
  client,
  userId,
}: ToolExecuteFunctionFactoryInput): ToolExecuteFunction<any> {
  const { name: toolName } = zodToolSchema;

  return async (input: unknown) => {
    try {

      // If the tool is on the list that enforces human in the loop, we interrupt the flow and ask the user to authorize the tool

      if (TOOLS_WITH_APPROVAL.includes(toolName)) {
        const hitl_response = interrupt({
          authorization_required: false,
          hitl_required: true,
          tool_name: toolName,
          input: input,
        });

        if (!hitl_response.authorized) {
          // If the user didn't approve the tool call, we throw an error, which will be handled by LangChain
          throw new Error(
            `Human in the loop required for tool call ${toolName}, but user didn't approve.`
          );
        }
      }

      // Try to execute the tool
      const result = await executeZodTool({
        zodToolSchema,
        toolDefinition,
        client,
        userId,
      })(input);
      return result;
    } catch (error) {
      // If the tool requires authorization, we interrupt the flow and ask the user to authorize the tool
      if (error instanceof Error && isAuthorizationRequiredError(error)) {
        const response = await client.tools.authorize({
          tool_name: toolName,
          user_id: userId,
        });

        // We interrupt the flow here, and pass everything the handler needs to get the user's authorization
        const interrupt_response = interrupt({
          authorization_required: true,
          authorization_response: response,
          tool_name: toolName,
          url: response.url ?? "",
        });

        // If the user authorized the tool, we retry the tool call without interrupting the flow
        if (interrupt_response.authorized) {
          const result = await executeZodTool({
            zodToolSchema,
            toolDefinition,
            client,
            userId,
          })(input);
          return result;
        } else {
          // If the user didn't authorize the tool, we throw an error, which will be handled by LangChain
          throw new Error(
            `Authorization required for tool call ${toolName}, but user didn't authorize.`
          );
        }
      }
      throw error;
    }
  };
}
````

### Create the tool retrieval helper

The last helper function of this module is the `getTools` helper. This function will take the configurations you defined in the `main.ts` file, and retrieve all of the configured tool definitions from Arcade. Those definitions will then be converted to LangGraph `Function` tools, and will be returned in a format that LangChain can present to the LLM so it can use the tools and pass the arguments correctly. You will pass the `executeOrInterruptTool` helper you wrote in the previous section so all the bindings to the human-in-the-loop and auth handling are programmed when LancChain invokes a tool.


````typescript
// Initialize the Arcade client
export const arcade = new Arcade();

export type GetToolsProps = {
  arcade: Arcade;
  toolkits?: string[];
  tools?: string[];
  userId: string;
  limit?: number;
}


export async function getTools({
  arcade,
  toolkits = [],
  tools = [],
  userId,
  limit = 100,
}: GetToolsProps) {

  if (toolkits.length === 0 && tools.length === 0) {
      throw new Error("At least one tool or toolkit must be provided");
  }

  // Todo(Mateo): Add pagination support
  const from_toolkits = await Promise.all(toolkits.map(async (tkitName) => {
      const definitions = await arcade.tools.list({
          toolkit: tkitName,
          limit: limit
      });
      return definitions.items;
  }));

  const from_tools = await Promise.all(tools.map(async (toolName) => {
      return await arcade.tools.get(toolName);
  }));

  const all_tools = [...from_toolkits.flat(), ...from_tools];
  const unique_tools = Array.from(
      new Map(all_tools.map(tool => [tool.qualified_name, tool])).values()
  );

  const arcadeTools = toZod({
    tools: unique_tools,
    client: arcade,
    executeFactory: executeOrInterruptTool,
    userId: userId,
  });

  // Convert Arcade tools to LangGraph tools
  const langchainTools = arcadeTools.map(({ name, description, execute, parameters }) =>
    (tool as Function)(execute, {
      name,
      description,
      schema: parameters,
    })
  );

  return langchainTools;
}
````

## Building the Agent

Back on the `main.ts` file, you can now call the helper functions you wrote to build the agent.

### Retrieve the configured tools

Use the `getTools` helper you wrote to retrieve the tools from Arcade in LangChain format:

````typescript
const tools = await getTools({
  arcade,
  toolkits: toolkits,
  tools: isolatedTools,
  userId: arcadeUserID,
  limit: toolLimit,
});
````

### Write an interrupt handler

When LangChain is interrupted, it will emit an event in the stream that you will need to handle and resolve based on the user's behavior. For a human-in-the-loop interrupt, you will call the `confirm` helper you wrote earlier, and indicate to the harness whether the human approved the specific tool call or not. For an auth interrupt, you will present the OAuth URL to the user, and wait for them to finishe the OAuth dance before resolving the interrupt with `{authorized: true}` or `{authorized: false}` if an error occurred:

````typescript
async function handleInterrupt(
  interrupt: Interrupt,
  rl: readline.Interface
): Promise<{ authorized: boolean }> {
  const value = interrupt.value;
  const authorization_required = value.authorization_required;
  const hitl_required = value.hitl_required;
  if (authorization_required) {
    const tool_name = value.tool_name;
    const authorization_response = value.authorization_response;
    console.log("⚙️: Authorization required for tool call", tool_name);
    console.log(
      "⚙️: Please authorize in your browser",
      authorization_response.url
    );
    console.log("⚙️: Waiting for you to complete authorization...");
    try {
      await arcade.auth.waitForCompletion(authorization_response.id);
      console.log("⚙️: Authorization granted. Resuming execution...");
      return { authorized: true };
    } catch (error) {
      console.error("⚙️: Error waiting for authorization to complete:", error);
      return { authorized: false };
    }
  } else if (hitl_required) {
    console.log("⚙️: Human in the loop required for tool call", value.tool_name);
    console.log("⚙️: Please approve the tool call", value.input);
    const approved = await confirm("Do you approve this tool call?", rl);
    return { authorized: approved };
  }
  return { authorized: false };
}
````

### Create an Agent instance

Here you create the agent using the `createAgent` function. You pass the system prompt, the model, the tools, and the checkpointer. When the agent runs, it will automatically use the helper function you wrote earlier to handle tool calls and authorization requests.

````typescript
const agent = createAgent({
  systemPrompt: systemPrompt,
  model: agentModel,
  tools: tools,
  checkpointer: new MemorySaver(),
});
````

### Write the invoke helper

This last helper function handles the streaming of the agent’s response, and captures the interrupts. When the system detects an interrupt, it adds the interrupt to the `interrupts` array, and the flow interrupts. If there are no interrupts, it will just stream the agent’s to your console.

````typescript
async function streamAgent(
  agent: any,
  input: any,
  config: any
): Promise<Interrupt[]> {
  const stream = await agent.stream(input, {
    ...config,
    streamMode: "updates",
  });
  const interrupts: Interrupt[] = [];

  for await (const chunk of stream) {
    if (chunk.__interrupt__) {
      interrupts.push(...(chunk.__interrupt__ as Interrupt[]));
      continue;
    }
    for (const update of Object.values(chunk)) {
      for (const msg of (update as any)?.messages ?? []) {
        console.log("🤖: ", msg.toFormattedString());
      }
    }
  }

  return interrupts;
}
````

### Write the main function

Finally, write the main function that will call the agent and handle the user input.

Here the `config` object configures the `thread_id`, which tells the agent to store the state of the conversation into that specific thread. Like any typical agent loop, you:

1. Capture the user input
2. Stream the agent's response
3. Handle any authorization interrupts
4. Resume the agent after authorization
5. Handle any errors
6. Exit the loop if the user wants to quit

````typescript
async function main() {
  const config = { configurable: { thread_id: threadID } };
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log(chalk.green("Welcome to the chatbot! Type 'exit' to quit."));
  while (true) {
    const input = await rl.question("> ");
    if (input.toLowerCase() === "exit") {
      break;
    }
    rl.pause();

    try {
      let agentInput: any = {
        messages: [{ role: "user", content: input }],
      };

      // Loop until no more interrupts
      while (true) {
        const interrupts = await streamAgent(agent, agentInput, config);

        if (interrupts.length === 0) {
          break; // No more interrupts, we're done
        }

        // Handle all interrupts
        const decisions: any[] = [];
        for (const interrupt of interrupts) {
          decisions.push(await handleInterrupt(interrupt, rl));
        }

        // Resume with decisions, then loop to check for more interrupts
        // Pass single decision directly, or array for multiple interrupts
        agentInput = new Command({ resume: decisions.length === 1 ? decisions[0] : decisions });
      }
    } catch (error) {
      console.error(error);
    }

    rl.resume();
  }
  console.log(chalk.red("👋 Bye..."));
  process.exit(0);
}

// Run the main function
main().catch((err) => console.error(err));
````

## Running the Agent

### Run the agent

```bash
bun run main.ts
```

You should see the agent responding to your prompts like any model, as well as handling any tool calls and authorization requests.

## Next Steps

- Clone the [repository](https://github.com/arcade-agents/ts-langchain-GoogleCalendar) and run it
- Add more toolkits to the `toolkits` array to expand capabilities
- Customize the `systemPrompt` to specialize the agent's behavior
- Explore the [Arcade documentation](https://docs.arcade.dev) for available toolkits

