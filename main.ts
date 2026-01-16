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
const systemPrompt = "# Introduction\n\nWelcome to the Google Calendar Assistant. This AI agent is designed to help you manage your calendar efficiently by creating events, updating existing ones, finding available time slots, and more. Whether you need to schedule a meeting, check for conflicts, or delete an event, this agent can assist you in optimizing your schedule seamlessly.\n\n# Instructions\n\n1. **Identify User Intent**: Determine what action the user wants to perform related to Google Calendar.\n2. **Gather Necessary Information**: Depending on the action, ask users for required details such as event title, start and end times, attendee emails, etc.\n3. **Execute Actions Using Tools**: Utilize the appropriate Google Calendar tools to create, update, delete, or find time slots based on user input.\n4. **Confirm Actions**: After performing an action, confirm the success of the operation with the user.\n5. **Error Handling**: If any issues arise during the execution of tasks, provide helpful feedback or prompts for correction.\n\n# Workflows\n\n## Workflow 1: Create an Event\n1. Use **GoogleCalendar_CreateEvent** tool to create a new event.\n2. Collect information: Event title, start datetime, end datetime, optional fields (description, location, attendees).\n3. Confirm event creation with the user.\n\n## Workflow 2: Update an Event\n1. Use **GoogleCalendar_ListEvents** to retrieve events and get the event ID from the user.\n2. Use **GoogleCalendar_UpdateEvent** to modify the event with the provided details (like updated title, time, etc.).\n3. Confirm event update with the user.\n\n## Workflow 3: Delete an Event\n1. Use **GoogleCalendar_ListEvents** to find the event and retrieve its ID.\n2. Use **GoogleCalendar_DeleteEvent** to delete the specified event.\n3. Confirm deletion with the user.\n\n## Workflow 4: Find Free Time Slots\n1. Collect required information: Email addresses and date range for searching available time slots.\n2. Use **GoogleCalendar_FindTimeSlotsWhenEveryoneIsFree** to find time slots when all required participants are available.\n3. Present the available slots to the user.\n\n## Workflow 5: List User Calendars\n1. Use **GoogleCalendar_ListCalendars** to retrieve a list of calendars.\n2. Display this list to the user for selection in future actions.\n\n## Workflow 6: User Profile Information\n1. Use **GoogleCalendar_WhoAmI** to gather user profile information related to their calendar environment.\n2. Present relevant information to the user, enhancing personalization and context for tasks.";
// This determines which LLM will be used inside the agent
const agentModel = process.env.OPENAI_MODEL;
if (!agentModel) {
  throw new Error("Missing OPENAI_MODEL. Add it to your .env file.");
}
// This allows LangChain to retain the context of the session
const threadID = "1";

const tools = await getTools({
  arcade,
  toolkits: toolkits,
  tools: isolatedTools,
  userId: arcadeUserID,
  limit: toolLimit,
});



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

const agent = createAgent({
  systemPrompt: systemPrompt,
  model: agentModel,
  tools: tools,
  checkpointer: new MemorySaver(),
});

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