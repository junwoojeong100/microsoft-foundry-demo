"""Narration script (English) — key → sentence, same keys as script_ko.py so every scene in scenes.py can use either language.

Captions and the SRT use the text exactly as written here; tts.py swaps product names and acronyms for a spoken form (PRONOUNCE) only in the audio.

Video structure
  · Opening, architecture and the real `azd up` run
  · Employee experience — a ChatGPT-style app, 'Contoso AI' (4 agents + general chat + safety)
  · Admin experience — the real Foundry portal (models, agents, guardrails, tracing, evaluation, operations)
  · Enterprise adoption checklist and wrap-up

The text avoids stating values that change from run to run. Values that appear on screen (such as evaluation scores) are checked
against the screen by the scene code.
"""

SCRIPT: dict[str, str] = {
    # ── 0. Opening
    "0_title": "Hello. In the next few minutes, I'll introduce Microsoft Foundry with a demo we built ourselves. "
               "Contoso AI, which you'll see today, is the internal AI service of a fictional manufacturer called Contoso. "
               "Employees use it like ChatGPT, and administrators run it in the Foundry portal. "
               "Everything on screen is the result of a real run on Azure.",
    "0_problem": "Many companies succeed with an AI pilot. But the moment they try to scale it across the company, they hit walls. "
                 "First, you have to connect your own documents and systems securely. Second, you have to keep choosing which model to use, "
                 "among a flood of new ones. Third, you have to prove quality and security even after you go live. "
                 "Foundry solves all three on one platform.",
    "0_what": "Microsoft Foundry is one platform where enterprises build and run AI apps and agents. At the top are your apps and business systems. "
              "Below them sit models and agents, tools and knowledge. Guardrails, evaluation and tracing live in the same project, "
              "and all of it rests on Entra ID, Azure's permission system, networking and monitoring. "
              "In other words, instead of collecting parts and bolting them together, you start from a platform that is already connected.",
    "0_agenda": "Today has four parts. First, we deploy everything with a single command. Next, the app that employees use: agents that answer from documents, "
                "handle tasks, and analyze data. Then it's the administrator's turn. We'll see models, agents, guardrails, tracing and evaluation "
                "in the real Foundry portal, exactly as it is. Finally, we wrap up with an enterprise adoption checklist.",
    # ── 1. Architecture
    "1_arch": "The architecture is simple. Employees use the Contoso AI app running on Container Apps, and the app reaches the Foundry project with Entra ID, "
              "with no keys. Inside the project are nine models, including GPT-6.1; agents that use tools such as document search and code execution; "
              "guardrails that protect inputs and outputs; and evaluation and tracing to measure quality. "
              "Administrators run the same project directly in the Foundry portal. And everything lives in a single region, Korea Central.",
    # ── 2. Real deployment (azd up)
    "2_cmd": "Deployment is a single command: azd up. What you're about to see is a recording of a real run, with the waiting time compressed.",
    "2_pre": "First, the pre-flight checks. It verifies the required resource providers and generates the demo access code automatically.",
    "2_infra": "Next, a Bicep template creates the infrastructure: the Foundry resource and project, and nine models. That's GPT-6.1 Sol and Terra, Model Router, "
               "embeddings, plus DeepSeek, Kimi, Llama, Mistral and Grok. The guardrail policy, the Application Insights connection "
               "and the least-privilege role assignments are in the same template.",
    "2_build": "Then the container image. Even without Docker on your machine, Azure Container Registry builds it for you, and the image is deployed to Container Apps.",
    "2_boot": "Finally, when the app starts for the first time, it uploads eight policy PDFs to a vector store and creates four agents in Foundry. "
              "That wait is handled automatically, too.",
    "2_done": "And that's everything. The web address and the access code are printed. In production, you would replace this code with Entra ID sign-in.",
    # ── 3. Employee experience: Contoso Guide
    "4_login": "Now, the app that employees see. Enter the access code and a ChatGPT-style screen opens. On the left are agents for each kind of work, "
               "and your conversation history builds up below.",
    "4_q1": "Let's ask Contoso Guide first. I've been here four years, so how many days of annual leave do I get this year, and how do I request a half day?",
    "4_steps": "You can watch the agent work. It turns the question into search queries and finds relevant passages in the policy documents, "
               "and you can even see the document names and relevance scores.",
    "4_ans": "The answer is sixteen days, based on the HR-001 employment rules. Click a source and the original PDF opens. "
             "That one line is what reduces hallucinations and builds trust.",
    "4_q2": "Let's try a harder one. A team dinner for twelve people, 480,000 won, with alcohol included. Can it be reimbursed, and who approves it?",
    "4_ans2": "It applies the meal limit and the alcohol rule together, and even shows the calculation. "
              "Whether this answer matches the policy exactly, we'll verify later with the evaluation in the admin view.",
    # ── 4. Contoso Pay
    "5_intro": "This time, instead of an answer, let's hand over a task. We upload a team-dinner receipt to Contoso Pay.",
    "5_vision": "From the photo of the receipt, it reads the merchant, the items and the amounts, and even tells whether alcohol is on it. "
                "It looks up the meal limit in the policy and calculates the claimable amount step by step.",
    "5_function": "Then it looks up the employee by ID and calls a function to submit the expense. This part matters. "
                  "We configured submission to run only after a person approves it.",
    "5_approve": "The claimed amount and the personal share are laid out, and when you click approve, a ticket number is issued. "
                 "You hand the work to AI, but the responsibility stays with a person.",
    # ── 5. Contoso Analyst
    "6_intro": "Next is data analysis. We ask Contoso Analyst, which is connected to the sales and customer feedback files, to look for anomalies.",
    "6_code": "The agent writes Python code itself and runs it in a sandbox. The calculation is not the model's guess. It is the result of actually running code.",
    "6_code2": "If we expand a finished step, the code the agent wrote appears as it is. You can verify exactly which calculations were done.",
    "6_result": "Here is the result. It found that robot vacuum revenue in the Busan-Gyeongnam region turned down from July and returns went up, "
                "and it linked that to customer feedback from the same period, most of which complains about the battery. The chart can be downloaded as a file.",
    # ── 6. Contoso Architect
    "7_mcp": "Questions about the latest technology go to Contoso Architect, which is connected to the Microsoft Learn MCP server. "
             "The basis is not the model's memory, but official documentation it has just searched. Tools are added by connecting them, without changing code.",
    "7_mcp2": "In the tool call list, the sequence stays visible. It searches Microsoft Learn for documents, then looks for code samples. "
              "The commands in the answer are based on the official documentation it just retrieved.",
    # ── 7. General chat and model choice
    "9_chat1": "There is also a general chat with no agent. It is the closest to ChatGPT, and you pick the model at the top. "
               "Let's turn on web search and ask about the European Union battery regulation obligations a manufacturer needs to know.",
    "9_chat2": "It searched the latest web and answered with source links. You can also see which model produced the answer, how long it took, and the token count.",
    "9_chat3": "Now let's change only the model, on the same screen. Not OpenAI this time, but DeepSeek. "
               "We'll ask it to write an apology text message for customers who complained about the battery.",
    "9_chat4": "The screen stays the same and only the model changed, because the call goes to the same endpoint of the same project.",
    "9_chat5": "Finally, let's pick Model Router. It looks at how hard the question is, chooses a suitable model by itself, and shows below which model actually answered. "
               "The platform even takes the burden of choosing a model off you.",
    # ── 8. Safety (inside the chat)
    "10_pii": "Now, security. It happens all the time that an employee pastes customer information as it is. Let's turn on personal data masking and send it.",
    "10_pii2": "It found the name, the ID number and the phone number and masked them, and only the masked sentence is passed to the model. "
               "The original text is not left in the chat history or the title, either.",
    "10_jb": "Next is a jailbreak attempt. Let's send the classic attack that tells the model to ignore its previous instructions.",
    "10_block": "The Foundry guardrail blocked it before the model was even called, and it tells the employee which policy it hit. "
                "Administrators manage this policy in the portal.",
    # ── 9. Agents as code
    "8_code1": "A quick pause. Let's look at how the agents we've seen so far were built, in code. This is the whole definition: "
               "the model deployment name, the instructions, and a list of tools. "
               "Add the document search tool and you get a knowledge agent. Add the code interpreter and you get an analyst. Add an MCP server address and you get an architect. "
               "Change the instructions or tools and recreate it, and a new version appears that you can compare with the previous one in the portal.",
    "8_code2": "Calling it is even simpler. You connect with Entra ID instead of a key, and just tell the Responses API the agent's name. "
               "When you stream, the tool calls, sources and token counts arrive as events, and our web screen simply draws those events. "
               "Now let's move on to the administrator's screen, where these agents are operated.",
    # ── 10. Admin experience: Foundry portal
    "A1_home": "Administrators start in the Foundry portal. The project we just deployed is open. You can see the project endpoint, "
               "and it shows that API key authentication is not used. Both apps and people come in only through Entra ID and role permissions.",
    "A2_catalog": "The catalog gathers models from many companies: OpenAI, Anthropic, Microsoft, Meta, Mistral and DeepSeek. Find the model you want and deploy it right away.",
    "A3_deploy": "This is the deployments screen. All nine models the app was using are here: GPT-6.1 Sol and Terra, Model Router, embeddings, "
                 "and DeepSeek, Kimi, Llama, Mistral and Grok, managed in the same project in the same way.",
    "A4_deploy2": "Open one deployment and you see its endpoint, its deployment type, and the tokens-per-minute limit. "
                  "It shows that keys can't be used, and adding or swapping a model also happens on this screen.",
    "A5_agents": "This is the agents screen. The four agents created from code are running, and the knowledge agent has already reached version two.",
    "A6_agent": "Open one and you see the model, the instructions and the connected tools as they are. The knowledge agent has file search connected. "
                "From here you can edit the instructions, chat with it right away, and even save it as a new version.",
    "A7_yaml": "The same definition is also available as YAML, so you can put it in Git and run it through code review and deployment pipelines.",
    "A8_publish": "In the details, you check the response endpoint and the publishing channels. You can publish to Teams, Microsoft 365 Copilot or a web app, "
                  "which takes the agent into the tools your employees already use.",
    "A9_guard": "This is the guardrails screen. The Contoso guardrail we deployed as code is applied to the two GPT-6.1 deployments and to Model Router.",
    "A9_guard2": "Jailbreak, indirect prompt injection and four content safety categories are all on, and you can expand any item to see its criteria. "
                 "The request that was blocked in the app earlier was blocked by exactly this policy.",
    "A10_trace": "Now, tracing. Every question an employee asked in the app is recorded here. You can see how long it took and the input and output tokens, "
                 "and some have evaluation scores attached.",
    "A11_trace2": "Open one and you see how long each step took, from the app's request to the agent call, the document search and the model call. "
                  "When an answer is slow or odd, you can find the step that caused it right away.",
    "A12_eval": "Finally, the most important question: how do we know it really got better? This evaluation scored the version before we connected knowledge "
                "and the version after, on the same twenty-two questions.",
    "A13_eval2": "Version two, with knowledge connected, passed most of the items, while version one, without it, falls far short. "
                 "You prove improvement with numbers, not with a feeling, and before deployment you can run the same evaluation to stop a version whose quality drops.",
    "A14_ops": "For administrators responsible for operations, there is the Operate screen. You see every project and agent in the subscription at a glance, "
               "with the number of running agents, the success rate, cost and alerts.",
    "A15_quota": "In Management, the Quota screen shows each deployment's tokens-per-minute limit and usage, and lets you request an increase. "
                 "It's the screen that keeps responses from suddenly getting blocked.",
    "A16_project": "In the project details you manage roles per user, and under connected resources you confirm that Application Insights, which collects the traces, "
                   "is already connected to this project. Employees use the app, administrators operate in the portal, and both look at the same project.",
    # ── 11. Enterprise adoption and wrap-up
    "12_ent": "Here are the questions that come up first in enterprise adoption. First, access control. Entra ID and Azure role-based access control separate what people and apps can do, "
              "and even this demo connects with a managed identity, with no keys. "
              "Second, networking. Private endpoints and virtual networks can close off internet exposure. "
              "Third, data. Customer prompts and data are not used to train the base models, and stored data is encrypted. "
              "Fourth, where data is processed. You choose the resource region and the deployment type to meet your requirements. "
              "Fifth, security and governance. Defender, Purview and Azure Policy carry threat detection and policy forward. "
              "Sixth, cost. You cap each deployment with a quota, and reserve provisioned throughput when you need stable performance. "
              "We configured this demo with a public endpoint for demonstration purposes. In production, turning these items on is the next step.",
    "11_sum": "To sum up. First, a single command deploys models, agents, guardrails and observability. Second, employees get answers from documents and get work done in a ChatGPT-style app. "
              "Third, administrators operate models, agents, guardrails, tracing and evaluation in one place, the Foundry portal. "
              "Fourth, security and quality are proven with code and with numbers.",
    "11_next": "The next step is simple. Pick one highly repetitive task, connect the related documents, and write twenty evaluation questions. "
               "Deploy everything you saw today yourself, with this repository. Thank you.",
}

# Chapter cards. compose.py builds the video's chapter list from the scene order.
CHAPTERS = [
    ("2", "Deploy", "azd up — a recording of the real run"),
    ("3", "Employee experience · Contoso AI", "One ChatGPT-style app with agents and models"),
    ("4", "Admin experience · Foundry portal", "Models · agents · guardrails · tracing · evaluation — the real portal screens"),
]
