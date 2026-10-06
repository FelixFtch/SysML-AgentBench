# AI, MCP and agent capabilities of SysML v2 tool vendors (checked 2026-10-02)

Purpose: answer "do the vendor tools already have agent capabilities, how far do they go, and where are their limits", to decide their role in SysML-AgentBench. Sources fall into three kinds and are labeled as such: **official documentation / official releases**, **demonstration posts by vendor employees in community forums**, and **third-party / community projects and user feedback**. No vendor AI feature was run by us.

## 1. Conclusions first

| Vendor / tool | Built-in AI generation | Official MCP | Community MCP | Headless interface an agent can use | Usable for us |
|---|---|---|---|---|---|
| **Dassault CATIA Magic / Cameo** | **Yes**: the built-in AI Assistant in 2026x (generates candidate architectures from stakeholder needs), plus the LEO Virtual Companion on the 3DEXPERIENCE platform for analysis and refinement | **Prototype / early access**: "CATIA Magic SysML v2 MCP (based on the Teamwork Cloud REST API)", demonstrated twice by a Dassault employee (2025-12 and 2026-02); the download link is behind the community login | `ajhcs/cameo-mcp-bridge` (MIT, 162 tools, **SysML v1 only**); `jgs-magic-sysmlv2-mcp` (commercial) | The OMG standard REST API of Teamwork Cloud (needs an enterprise server); no official headless validation CLI on the desktop | The AI Assistant needs a Magic Cyber Systems Engineer / SoS Architect 2026x license (whether the Community Edition includes it is **unconfirmed**, most likely not); the MCP needs a TWC server → **essentially out of reach** for this project unless Bollas's license is the full 2026x edition |
| **Sensmetry Syside** | No generation; positioned as "models your AI can read and write" | **Not yet**; the roadmap **promises for 2026 Q3** "Syside & Sysand MCP servers for Claude, Copilot"; no release announcement as of 10-02 | User-built: wrapping the `syside check` CLI as an MCP server or a Claude Code skill (forum, 2026-03/05) | `syside check` CLI and the Python Automator API (both in the paid Modeler/Automator); Syside Cloud ships with Claude Code preinstalled | The CLI needs a paid plan or trial; methodologically the same as ours (checker in the loop) |
| **Eclipse SysON (Obeo)** | Prototype: a 2025-05 blog post demonstrates an LLM assistant (Mattermost interface); the enterprise price list says "AI Integration: Soon" | None | `Casys-AI/mcp-syson` (MIT, 31 tools: editing, AQL queries, requirement tracing, diagrams, value read/write; self-hosted) | GraphQL / Sirius Web API; SysML v2 standard API exchange | Usable (self-hosted Docker) as a fallback for graphical viewing and "read the model" tools |
| **Siemens Systems Modeler for SysML v2** | No public AI feature found | None | None | REST / OSLC | No license; not considered |
| **OMG official API services (pilot)** | — | — | `jgs-sysmlv2-api-mcp` (proprietary license, 35 tools, staged commits, one branch per agent session; works with any OMG standard API endpoint, including the official pilot and TWC); `redsteve/SysML-v2-API-MCP-Server` (MIT, C++) | OMG Systems Modeling API 1.0 REST (we have cloned `SysML-v2-API-Services`, not deployed) | Deployable; the **standard interoperability layer** connecting Cameo TWC, SysON and the official implementation |

**No vendor offers a way to judge whether a model is right in engineering terms.** Every AI/MCP product falls into one of three kinds: ① pipes that let an agent **read and write** models (API/MCP); ② **syntax/consistency checkers** (CLI); ③ Dassault's "generate a candidate architecture → a person refines it" assistant (**no public evaluation data**).

## 2. Vendor by vendor

### 2.1 Dassault Systèmes (CATIA Magic / Cameo)

**Official sources**
- Product matrix (docs.nomagic.com, 2022x–2026x): the `AI Assistant` row appears under **Magic Cyber Systems Engineer 2026x / 2026x Refresh1, Magic Systems of Systems Architect, MagicDraw and Cameo Systems Modeler**. The `SysML v2` row also starts at 2026x.
- Webinar "AI for SysML v2" (events.3ds.com): demonstrates "the built-in AI Assistant generates initial candidate architectures from stakeholder needs → the LEO Virtual Companion (3DEXPERIENCE platform) analyzes and refines them iteratively"; the agenda explicitly includes "where engineering judgment is still needed".
- Webinar "Integrating Tools Using AI Within SysML v2" (Daniel Brookshier, member of the OMG Architecture Board): the topic is using **off-the-shelf coding agents such as Codex and Claude Code to write Cameo plug-ins and SysML v2 Open API scripts**, including "agents, test harnesses, best practices". → Dassault's stance: coding agents act as **extension developers** that operate on models through the REST API.
- SysML v2 Community Edition (free): 100% standard-conformant, text and diagrams synchronized both ways, **≤ 500 main elements**, aimed at learning. The page **does not mention** the AI Assistant.
- Teamwork Cloud: fully conforms to the OMG SysML v2 API & Services; CI/CD can create, query and evaluate; a proprietary Model Evaluation extension also exists.

**Community posts by a vendor employee (3DSwym, author "SP")**
- 2025-12-18: "SysML v2 Simulation, 3D CAD Result Visualization, and Report Generation using MCP": MCP chains simulation, CAD and reports.
- 2026-02-24: "Jama MCP + CATIA Magic SysML v2 MCP": requirements extracted from a SysML v2 simulation → pushed to Jama → test cases generated → read back to run the simulation → results written back to Jama. The post ends with "CATIA Magic SysML v2 MCP (TWC REST API based) is available at -" (the link requires a login).
- Another post (a robot-arm digital twin) explicitly says "prototype demo".

**Third parties**
- `ajhcs/cameo-mcp-bridge` (MIT, created 2026-03, 21 stars, 162 tools, a Java plug-in connected to a running Cameo): native validation, report wizard, requirement import/export (JSON/CSV), simulation preview, read-only Teamwork probes. **Known limits**: diagram layout is the main pain point; elements cannot be re-owned; no batch operations; pure request/response without events; **"SysML v2 profile support" is listed under "contributions welcome", i.e. v1 only for now**.
- `jgsystemsconsulting/jgs-magic-sysmlv2-mcp`: drives a running Cameo for v2, **proprietary license** (free tier plus a PRO license file).

**The limit of what it can do (from public information)**
- Generation: exists, but as a black box (which LLM, which prompts, and whether third-party models can be configured are not public); the output is a "candidate architecture", and Dassault itself lists human refinement as a required step; there is no public success rate or quality data.
- MCP: real and usable for integration demonstrations (Jama, simulation, CAD), but **tied to an enterprise Teamwork Cloud server**; not usable with the desktop Community Edition.
- Headless validation: no official CLI on the desktop; only through the TWC API or a community bridge.

### 2.2 Sensmetry (Syside / Sysand)

**Official sources**
- Product page: "With Syside, your AI assistant can read your models and contribute to them." This refers to the CLI/Python API, not built-in generation.
- Roadmap 2026 Q1: Syside Cloud "pre-configured with Syside Modeler, Automator, Sysand, **and Claude Code**", 1000+ users.
- Roadmap 2026 Q2 (2026-05-13): Q3 goals include "**Syside & Sysand MCP servers** — to make it even easier for AI assistants (Claude, Copilot, etc.) to work with your SysML v2 models"; Syside/Sysand reach v1 together; Derisker (ISO 26262/21434 safety analysis including STPA/FMECA/FTA) reaches a public stable release in Q3. As of 2026-10-02 no MCP release announcement was found.
- 0.9.0 (2026-05-10): requirement evaluation (`assumptions implies requirements`), ReqIF, the 2026-03 standard library.
- Licensing: the Editor is free (VS Code only); the `syside check` CLI and Automator are in the paid Solo/Business plans; 30-day trial.

**User feedback (forum thread "Claude Code / AI Agent Sharing Thread", 2026-03-13 to 05-21)**
- How the practice evolved: a home-made MCP wrapping `syside check` → replaced by a Claude Code **skill** (less JSON overhead); the CLI binary sits in the VS Code extension folder `bundled/syside-cli/bin/`.
- Combined with `nomograph/sysml` (from a GitLab team) to index models: look up elements by name and list related elements, instead of having the agent read a pile of text and infer the connections itself.
- A hand-written `sysml-patterns.md` prescribes modeling patterns (abstract parts plus multiplicity, rules for choosing ISQ attributes `:>` versus `:`, and so on).
- **The core open problem (verbatim)**: "defining what counts as 'good' modeling, aside from syntactically correct code… With better way to assess model quality, there could be a subagent write and check loop." This is exactly what this project's Q3 and gold assertions address.

**Limits**: no generation; the MCP is not released; the checker covers syntax and semantic consistency, not engineering correctness; behind a paywall.

### 2.3 Obeo (Eclipse SysON)

- Blog 2025-05-12: prototype "AI as a modeling assistant / AI as a natural-language interface to the model", LLM + SysON + Mattermost; states clearly that "AI is an assistant, not the decision maker"; productization planned.
- Obeo Enterprise for SysON price list: **AI Integration = Soon** (both the standard and custom editions).
- Community `Casys-AI/mcp-syson` (MIT, 31 tools in 7 groups, including 6 MCP App viewers; one-command Docker). A design note worth noting: the early **LLM-driven tools were removed**, because "the caller is already a language model; having the host run another model only adds indirection; generating SysML is the caller's job, and `syson_element_insert_sysml` does the writing".
- Limits: no official AI; the community MCP is for reading, writing and querying, with no judgment beyond validation.

### 2.4 Siemens

No public information on an AI assistant or MCP for Systems Modeler for SysML v2 was found (2026-10-02).

### 2.5 The standard API layer (vendor-neutral)

- `jgs-sysmlv2-api-mcp` v1.0.1/2.0.0: 35 tools in five groups (navigation and reading, staged writing, project life cycle, branches and tags, infrastructure); writes go through a **staged commit plus token confirmation**; supports "one branch per agent session"; ships plug-in manifests for Claude Code, Cursor, Codex and Gemini CLI; the documentation includes a recipe for "running the OMG reference pilot locally in Docker". Proprietary license (free plus PRO).
- Why it matters: **the OMG standard REST API is the only interface implemented by the official pilot, Cameo TWC and SysON alike**. With the official API services deployed, an agent can perform the same operations on all three back ends through one MCP server, which is something measurable on the Interoperability dimension.

## 3. Related academic work (same period)

- UC3M (e-archivo), "An agent-based approach for the automatic generation of valid SysMLv2 models in industrial contexts": an LLM agent + RAG (retrieving SysML v2 code examples) + a self-correcting loop with a formal validation engine; compares LLM_Raw / +RAG / +validation configurations, the same ablation shape as our P0/P2/P1.
- LangGraph multi-agent semantic validation (14 models, GPT-4o-mini vs DeepSeek-R1): the two models disagree on under-specified models, which supports "an LLM validator must itself be evaluated".

## 4. Implications for SysML-AgentBench

1. **Correcting an earlier judgment**: "Dassault only has marketing prototypes" was inaccurate. Dassault has built the AI Assistant into the 2026x product and uses a TWC-based SysML v2 MCP internally / in early access. Both sit behind **enterprise licenses and servers**, and the public information contains no quality data.
2. **A new optional candidate, P-VENDOR**: if Bollas's license is Magic Cyber Systems Engineer 2026x (with the AI Assistant), treat it as a "vendor black-box agent" on the T4 generation tasks: generate with its AI Assistant → export the .sysml text → run our official validation, assertions and engineering checks. This is very valuable to RTRC (they use Cameo), but first confirm that the license terms allow evaluation and publication.
3. **The design direction is confirmed by industry**: Obeo's community MCP ("generation is the caller's job; the tool only reads, writes and queries"), SEI's three layers, and Sensmetry users who use the CLI as the judge all match our "deterministic tool layer, generation separate from judgment".
4. **Nobody has solved "what is a good model"**: Sensmetry forum users, the Obeo blog and the Dassault webinars all list human judgment as required. Our gold assertions + engineering-semantic checks + failure classes answer this gap directly, and the report should cite these sources as evidence of the need.
5. **The standard API as an interoperability experiment** (optional, after week 6): deploy the official API services (already cloned) and, through `jgs-sysmlv2-api-mcp` or a thin bridge of our own, let the same agent operate on the official API back end; if TWC or SysON become available later, the same procedure compares back ends.
6. **Syside MCP**: wait for Sensmetry's release (planned for 2026 Q3); once released it can replace user-built CLI wrappers, and the judging logic stays the same.

## 5. To confirm

- Bollas's Cameo license: product name and version (Magic Cyber Systems Engineer / SoS Architect 2026x or not); whether it includes the AI Assistant; whether Teamwork Cloud is available; whether the license terms allow evaluation results to be published.
- How to obtain Dassault's SysML v2 MCP in practice (the link behind the community login) and its prerequisites.
- Whether Sensmetry's MCP has been released; the academic-license application.
