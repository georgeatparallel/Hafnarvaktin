Final project
In the final project you will design, build and evaluate an AI agent system for a case of your own choice.

The purpose of the project is to apply the concepts from the course in a realistic use case. You are not expected to build a complete agent framework from scratch. You are expected to design a bounded system that uses agents, tools, workflows and retrieval in a meaningful way.

You must choose a relevant case yourself and justify it. The project should result in a working system. It should not just be a sandbox or toy demo. You must test the system and show that it works in your chosen case.

Project type
This is an individual project. You can help each other, but you have to turn in your own project.

Scope
You must build a prototype of an AI agent system for a case of your own choice.

You must use NanoClaw or Hermes Agent. If you want to use a different platform, you must get approval from the teacher first.

The project is about building a useful and bounded AI agent system for a real use case.

Mandatory technical requirements
Your project must include:

MCP
n8n
Neo4j for vector RAG
Neo4j for graph RAG
These components must be used as meaningful parts of the system.

Functional requirements
Your system must:

support a clearly defined use case
use Neo4j vector RAG to retrieve relevant information from your corpus or project data
use Neo4j graph RAG to represent and use relationships between concepts, sources, requirements, arguments or tasks
expose at least one n8n workflow or RAG through an MCP server, so the agent can call it as a tool
support interaction with the user through a reasonable interface (e.g. Telegram, Discord, email, ..) Where the case calls for it, the system may use multiple agents with defined roles (e.g. an orchestrator and sub-agents). This is not required.
The exact functions of the system depend on your chosen case. The important thing is that the agent system solves a relevant problem in a meaningful way and that MCP, n8n, vector RAG and graph RAG are used as real parts of the solution.

Examples of relevant cases are:

a thesis or academic project support agent that tracks requirements, retrieves sources and monitors progress
a software development support agent that tracks issues, retrieves documentation and coordinates code reviews
a research assistant that manages literature, identifies gaps and summarizes findings
a customer support agent that retrieves product knowledge, handles common queries and escalates through workflows
a project management agent that tracks tasks, deadlines and team actions across a defined project
a content production assistant that tracks sources, story outlines and editorial tasks
a game companion agent that retrieves lore and guides, tracks quests or objectives and maps relationships between characters, factions and items in a chosen game
a personal trainer agent that tracks workouts and progress, retrieves training plans and nutrition guidance and maps relationships between goals, exercises and recovery
Suggested process
You should work through the project in roughly this order:

Investigate agent platforms and select a case.
Elicit and describe requirements.
Design the architecture.
Select and justify the agent platform and model setup.
Design how MCP, n8n, vector RAG and graph RAG are used together.
Set up and build the system.
Tweak, use and test the system.
Evaluate strengths, weaknesses and limitations.
Document the project.
Project plan
The project runs over 4 weeks:

Week 1: investigate agent platforms and select a case
Week 2: set up the system
Week 3: tweak and use the system
Week 4: write the report and hand in the project
Lectures
The lectures during the project period are planned as follows:

Week 1: start of project, walkthrough of project, introduction to NanoClaw and Hermes
Week 2: presentation of cases and architecture
Week 3: supervision and implementation (online)
Week 4: exam preparation and supervision
Deliverables
You must submit:

a working system
an architecture diagram
a report of max 5 pages
Report
The report must include:

choice of agent platform, model and architecture — including a reflection on model size, capabilities and cost
at least one prompt or skill created by you — either a custom skill in the agent platform or a prompt for an agent node in n8n — and an explanation of your design choices
implementation overview
use of the agent in the chosen case
reflection and future work
Maximum length: 5 pages.

A suggested structure is:

1 page on choice of agent platform and architecture
2 pages on implementation
1 page on use of the agent
1 page on reflection and future work
Evaluation
The project will be evaluated based on:

clarity of the use case
quality of the requirements
quality of the architecture and justification of model choice
quality of the student-created prompt or skill
meaningful use of MCP
meaningful use of n8n
meaningful use of vector RAG
meaningful use of graph RAG
quality of the demonstrated system in the oral exam
reflection on limitations, security and academic integrity
overall quality of the prototype and report
Oral exam
The project will be evaluated in the oral exam.

At the oral exam you must present and demonstrate your system. Here you should show your chosen case, your architecture, your implementation and how the system works in practice.
