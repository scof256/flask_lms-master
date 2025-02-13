from flask import Flask, render_template, jsonify, request, send_from_directory
import openai
import markdown

app = Flask(__name__)

# LLM Setup (Gemini)
OPENAI_API_KEY = "AIzaSyB67xwYbaD7vUCVYoJoRxG6FlFT5dEq-DQ"  # Replace with your actual key
model = "gemini-2.0-flash-exp"  # Or a suitable Gemini model

openai_client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# Data (Questions and Prompts)
questions = [
    {"id": 1, "category": "Key Definitions", "question": "What is Artificial Intelligence (AI) in simple terms?", "options": ["A computer system that mimics human intelligence", "A process that only involves manual calculations", "A machine that can only perform manual tasks", "A type of computer virus"], "correct": 0},
    {"id": 2, "category": "Key Definitions", "question": "What are the key differences between AI, machine learning, and deep learning?", "options": ["Machine learning and deep learning are not part of AI", "Deep learning is an outdated term for AI, while machine learning is a new term", "AI is a broad field, machine learning is a method to achieve AI through data learning, and deep learning is a specialized technique using neural networks", "All three terms refer to the exact same concept with no differences"], "correct": 2},
    {"id": 3, "category": "Key Definitions", "question": "How does AI process information compared to how humans think?", "options": ["AI processes information by randomly guessing outcomes", "AI and human thought are exactly identical in every way", "Humans process information in binary code, similar to computers", "AI uses algorithms and statistical models, while human thinking involves cognitive and emotional processing"], "correct": 3},
    {"id": 4, "category": "Real-world Impact", "question": "How is AI transforming different industries (healthcare, finance, education, etc.)?", "options": ["By only replacing outdated computer systems without any added benefits", "By creating more bureaucratic hurdles in every industry", "By eliminating human jobs entirely in every sector", "By automating tasks, enhancing data analysis, personalizing services, and improving decision-making processes"], "correct": 3},
    {"id": 5, "category": "Real-world Impact", "question": "What are some surprising ways AI is being used today?", "options": ["Solely for automating simple calculations", "Exclusively for military applications", "Primarily for creative arts, wildlife conservation, and predictive maintenance", "Only for repetitive manufacturing tasks"], "correct": 2},
    {"id": 6, "category": "Real-world Impact", "question": "How can AI impact job markets in the future?", "options": ["It can create new opportunities while displacing some traditional roles", "It will only eliminate jobs without creating any new ones", "It will have no effect on job markets at all", "It will replace every human worker in all industries"], "correct": 0},
    {"id": 7, "category": "Discover Prompt Engineering", "question": "What is prompt engineering, and why is it important when using AI?", "options": ["It is a way to manually override AI outputs", "It is irrelevant to AI performance", "It involves designing input queries to guide AI responses effectively", "It is only used in programming hardware devices"], "correct": 2},
    {"id": 8, "category": "Discover Prompt Engineering", "question": "What makes a good AI prompt? Give examples of good vs. bad prompts.", "options": ["A good prompt is one that is extremely short and leaves everything open", "A good prompt is one that uses slang and informal language exclusively", "A good prompt includes random unrelated information", "A good prompt is clear, specific, and provides context; a bad prompt is vague and ambiguous"], "correct": 3},
    {"id": 9, "category": "Discover Prompt Engineering", "question": "How do small changes in prompts affect AI responses?", "options": ["They only affect the speed of processing", "They have no effect on the outputs", "Minor modifications can lead to significantly different outputs", "They result in the AI refusing to answer"], "correct": 2},
    {"id": 10, "category": "LLM Fundamentals", "question": "What is a Large Language Model (LLM), and how does it work?", "options": ["It works by randomly generating words without any training", "It is a small database of pre-written responses", "It is an AI system that predicts and generates human-like language from large text datasets", "It is a tool exclusively for translating languages without any predictive capabilities"], "correct": 2},
    {"id": 11, "category": "LLM Fundamentals", "question": "How do LLMs learn from data?", "options": ["By adjusting internal parameters through training algorithms on large datasets", "By simply copying human-written text without any processing", "By operating on pre-programmed rules without data", "By memorizing every sentence without learning any patterns"], "correct": 0},
    {"id": 12, "category": "LLM Fundamentals", "question": "What are the limitations of LLMs when answering questions?", "options": ["They always provide factually correct and context-aware answers", "They have unlimited access to all real-time data", "They may produce plausible but incorrect answers and struggle with nuanced contexts", "They only function as simple calculators"], "correct": 2},
    {"id": 13, "category": "Crafting Effective Prompts", "question": "What are three techniques for making an AI prompt clearer and more useful?", "options": ["Using as few words as possible without details", "Being specific, providing context, and using step-by-step instructions", "Writing in a confusing manner intentionally", "Being vague, avoiding context, and using random instructions"], "correct": 1},
    {"id": 14, "category": "Crafting Effective Prompts", "question": "How does adding context improve AI responses?", "options": ["It only makes the prompt longer without any benefits", "It forces the AI to generate generic responses", "It helps AI understand background information for more accurate responses", "It confuses the AI by providing too much irrelevant detail"], "correct": 2},
    {"id": 15, "category": "Crafting Effective Prompts", "question": "How can you design a prompt that helps AI generate creative answers?", "options": ["By asking very strict, yes-or-no questions", "By including open-ended questions and creative constraints", "By avoiding any form of instruction", "By limiting the prompt to factual data only"], "correct": 1},
    {"id": 16, "category": "Iterative Refinement", "question": "What is iterative refinement, and how can it improve AI-generated content?", "options": ["Ignoring initial output and starting from scratch every time", "Repeatedly revising and enhancing outputs for clarity and accuracy", "A one-time generation process with no further revisions", "Automatically deleting unsatisfactory outputs without improvement"], "correct": 1},
    {"id": 17, "category": "Iterative Refinement", "question": "How can you refine a weak AI-generated response to make it better?", "options": ["By simply copying the weak response without changes", "By reducing the amount of context provided", "By providing additional context and clarifying instructions", "By completely ignoring any user feedback"], "correct": 2},
    {"id": 18, "category": "Iterative Refinement", "question": "What are common mistakes people make when refining AI-generated content?", "options": ["Always leaving the response unchanged", "Providing too much clear direction", "Using iterative refinement only once", "Over-editing, ambiguous context, and unclear objectives"], "correct": 3},
    {"id": 19, "category": "Few-shot Prompting", "question": "What is few-shot prompting, and how does it help AI understand instructions better?", "options": ["It overloads the AI with too many examples to confuse it", "It provides a few examples to guide the AI's understanding and response", "It relies on a single example to guide AI responses", "It gives the AI no examples at all"], "correct": 1},
    {"id": 20, "category": "Few-shot Prompting", "question": "How does few-shot prompting compare to zero-shot and one-shot prompting?", "options": ["All three methods provide the same level of instruction", "One-shot provides more examples than few-shot", "Few-shot uses several examples, one-shot uses one, and zero-shot uses none", "Zero-shot provides the most detailed guidance"], "correct": 2},
    {"id": 21, "category": "Few-shot Prompting", "question": "Can you create an example of a few-shot prompt for summarizing news articles?", "options": ["A prompt that provides examples of weather reports instead of news summaries", "A prompt including multiple examples of news summaries, then asking for a summary", "A prompt that only asks 'Summarize this article'", "A prompt that instructs the AI to ignore all given examples"], "correct": 1},
    {"id": 22, "category": "Applying AI for Productivity", "question": "How can AI help professionals be more productive in their daily tasks?", "options": ["By complicating simple tasks with unnecessary steps", "By only focusing on creative tasks", "By automating repetitive tasks and assisting with scheduling", "By replacing all human input completely"], "correct": 2},
    {"id": 23, "category": "Applying AI for Productivity", "question": "What are three AI-powered tools that can help with project management?", "options": ["Manual spreadsheets with no AI features", "Only email clients and calendar apps without AI integration", "Traditional paper planners", "Task automation software, AI-based scheduling tools, and intelligent analytics platforms"], "correct": 3},
    {"id": 24, "category": "Applying AI for Productivity", "question": "How can AI assist in writing, summarizing, and editing documents?", "options": ["By only providing spell-check functionalities", "By disregarding grammar and context completely", "By completely rewriting documents without user input", "By generating drafts, summarizing content, and suggesting edits"], "correct": 3},
    {"id": 25, "category": "Types of AI Tools", "question": "What are the main categories of AI tools, and what are they used for?", "options": ["They are all generic tools with no specialized functions", "Only tools for playing games", "From natural language processing to computer vision, used for tasks like text analysis and image recognition", "They are only used for data storage"], "correct": 2},
    {"id": 26, "category": "Types of AI Tools", "question": "How do AI-powered text generators differ from AI-powered image generators?", "options": ["Text generators can create visuals, while image generators can create text", "Text generators are only used for code, and image generators for videos", "They both generate identical content in the same format", "Text generators produce written content, and image generators create visuals using specialized algorithms"], "correct": 3},
    {"id": 27, "category": "Types of AI Tools", "question": "What are some AI-powered tools for automating repetitive office tasks?", "options": ["Only manual typewriters", "Email filtering, scheduling assistants, and data entry automation software", "Paper-based filing systems", "Traditional calculators"], "correct": 1},
    {"id": 28, "category": "Integration Strategies", "question": "What are the steps to successfully integrate AI into a business workflow?", "options": ["Implementing AI without any testing or assessment", "Only purchasing the most expensive AI tool without planning", "Immediately replacing all human workers with AI", "Assessing needs, selecting tools, piloting solutions, and scaling based on feedback"], "correct": 3},
    {"id": 29, "category": "Integration Strategies", "question": "What are some common challenges when integrating AI into existing work processes?", "options": ["Only issues with the physical hardware", "There are no challenges at all", "Just the color of the AI interface", "Data quality issues, resistance to change, and lack of technical expertise"], "correct": 3},
    {"id": 30, "category": "Integration Strategies", "question": "What are some examples of companies that have successfully adopted AI?", "options": ["Firms that solely focus on manual labor", "Tech giants like Google, Amazon, and IBM along with innovative startups", "Only small local businesses with no global presence", "Companies that completely avoid using any technology"], "correct": 1},
    {"id": 31, "category": "Responsible AI", "question": "What does 'responsible AI' mean, and why is it important?", "options": ["Only focusing on AI's technical performance without transparency", "Using AI without any ethical or societal considerations", "Developing AI ethically, transparently, and with societal considerations", "Developing AI solely for profit without concern for impact"], "correct": 2},
    {"id": 32, "category": "Responsible AI", "question": "What are three ethical concerns related to AI use in the workplace?", "options": ["There are no ethical concerns with AI", "Bias, privacy invasion, and lack of accountability", "Only concerns about AI's power consumption", "Only increased productivity"], "correct": 1},
    {"id": 33, "category": "Responsible AI", "question": "How can companies ensure they use AI in a responsible and ethical way?", "options": ["Ignoring ethical guidelines in favor of rapid deployment", "Focusing only on profits without considering ethics", "Implementing ethical guidelines, conducting regular audits, and ensuring transparency", "Relying solely on automated systems without oversight"], "correct": 2},
    {"id": 34, "category": "Identifying Bias and Harms", "question": "How does bias appear in AI models, and what are the consequences?", "options": ["Bias only makes AI models more efficient", "Bias is not possible in AI models", "Bias can emerge from training data leading to unfair outcomes and discrimination", "Bias in AI has no real-world consequences"], "correct": 2},
    {"id": 35, "category": "Identifying Bias and Harms", "question": "Can you find an example where AI produced biased or harmful results?", "options": ["An algorithm that treats all candidates equally without bias", "AI systems that always provide perfect, unbiased decisions", "A hiring algorithm that favored one gender due to biased historical data", "An example where AI caused harm in traffic signal timings"], "correct": 2},
    {"id": 36, "category": "Identifying Bias and Harms", "question": "What methods can be used to detect and reduce AI bias?", "options": ["Using only one type of training data without review", "Relying on biased data to test algorithms", "Ignoring bias and hoping it resolves on its own", "Bias audits, diverse datasets, and fairness testing"], "correct": 3},
    {"id": 37, "category": "Human-in-the-loop", "question": "What does 'human-in-the-loop' AI mean, and why is it useful?", "options": ["Relying on AI without any human input", "Involving human oversight to ensure accuracy, accountability, and ethics", "Removing humans entirely from the AI process", "Using humans only for manual tasks unrelated to AI"], "correct": 1},
    {"id": 38, "category": "Human-in-the-loop", "question": "How can human oversight improve AI decision-making?", "options": ["It is unnecessary if AI is powerful enough", "It slows down the process without any benefits", "It can catch errors, provide context, and guide AI decisions", "It only interferes with AI efficiency"], "correct": 2},
    {"id": 39, "category": "Human-in-the-loop", "question": "What industries benefit most from a human-in-the-loop AI approach?", "options": ["Only small-scale local businesses benefit", "All industries work best without any human oversight", "Industries like healthcare, finance, and autonomous vehicles benefit most", "Only the entertainment industry benefits"], "correct": 2},
    {"id": 40, "category": "Data Privacy and Security", "question": "How does AI handle sensitive data, and what are the risks?", "options": ["AI does not process sensitive data at all", "AI handles sensitive data without any security measures", "AI uses encryption and access controls, but risks include data breaches", "Sensitive data is never stored by AI systems"], "correct": 2},
    {"id": 41, "category": "Data Privacy and Security", "question": "What are three best practices for ensuring AI respects user privacy?", "options": ["Sharing user data openly to ensure transparency", "Using public networks for sensitive data", "Data anonymization, strict access controls, and regular security audits", "Ignoring data protection laws"], "correct": 2},
    {"id": 42, "category": "Data Privacy and Security", "question": "What are some real-world examples of AI-related data breaches?", "options": ["Data breaches only occur in non-AI systems", "Breaches in finance or healthcare due to poorly secured AI systems", "There have been no AI-related data breaches", "Data breaches are only a concern for personal computers"], "correct": 1},
    {"id": 43, "category": "Staying Current with AI", "question": "What are the best ways to stay updated on AI trends and developments?", "options": ["Staying off the internet entirely", "Only using social media rumors", "Following reputable tech news, academic journals, and industry blogs", "Ignoring all online resources and relying on outdated textbooks"], "correct": 2},
    {"id": 44, "category": "Staying Current with AI", "question": "What are some online courses or resources for continuous AI learning?", "options": ["Old radio broadcasts from decades ago", "Only in-person seminars with no online materials", "Random YouTube videos with no credentials", "Platforms like Coursera, edX, and MIT OpenCourseWare"], "correct": 3},
    {"id": 45, "category": "Staying Current with AI", "question": "How do AI experts predict the future of AI in the next five years?", "options": ["They believe AI will only be used in labs", "They predict continued advancements in automation, ethics, and integration", "They expect AI to replace all human jobs immediately", "They predict that AI will become obsolete"], "correct": 1},
    {"id": 46, "category": "Evaluating New AI Tools", "question": "What criteria should be used to evaluate the usefulness of a new AI tool?", "options": ["Its ability to completely replace human decision-making", "Only the tool's color and design", "Accuracy, scalability, usability, and ethical considerations", "How expensive the tool is, regardless of performance"], "correct": 2},
    {"id": 47, "category": "Evaluating New AI Tools", "question": "How can businesses decide whether an AI tool is worth adopting?", "options": ["By ignoring how it fits into existing systems", "By adopting every new tool regardless of relevance", "By choosing the tool with the flashiest marketing", "By assessing performance, integration, cost-effectiveness, and alignment with needs"], "correct": 3},
    {"id": 48, "category": "Evaluating New AI Tools", "question": "What are some red flags that an AI tool might not be trustworthy?", "options": ["High user ratings and detailed documentation", "Robust security measures", "Lack of transparency, poor performance data, and unclear data policies", "Widespread adoption by reputable companies"], "correct": 2},
    {"id": 49, "category": "Local and Global Examples", "question": "How is AI being used differently in various countries and cultures?", "options": ["Only developed countries use AI", "It is exactly the same in every country", "It varies based on local needs, regulations, and cultural attitudes", "It depends solely on the country's GDP"], "correct": 2},
    {"id": 50, "category": "Local and Global Examples", "question": "Can you find a case study of AI solving a local business problem?", "options": ["Local businesses do not use AI at all", "AI solving logistics, customer service, or supply chain issues", "AI case studies are only available for large multinational companies", "AI only causes more problems for local businesses"], "correct": 1}
]

prompts = [
    {"id": 7, "prompt_text": "Craft a prompt that instructs an AI to generate a concise summary of various content types—for example, a news article, a multi‑page report, legal documents, customer feedback, research articles, and executive briefings."},
    {"id": 8, "prompt_text": "Develop a prompt that asks the AI to provide clear definitions of technical or everyday terms and to explain a simple process step‑by‑step."},
    {"id": 9, "prompt_text": "Write a prompt that guides the AI to produce internal messages—such as a polite email reply and a brief company update—in a professional tone."},
    {"id": 10, "prompt_text": "Create a prompt that directs the AI to generate a meeting agenda, convert raw meeting minutes into an actionable plan, produce a detailed to‑do list, and suggest follow‑up tasks."},
    {"id": 11, "prompt_text": "Formulate a prompt that asks you to list everyday work tasks that could be streamlined or improved with AI assistance."},
    {"id": 12, "prompt_text": "Design a prompt exercise where you compare two different prompt phrasings, reflect on their outcomes, and collaborate with peers to refine your prompts."},
    {"id": 13, "prompt_text": "Create several versions of a single prompt using varying lengths and compare how the differences affect the AI’s response detail and quality."},
    {"id": 14, "prompt_text": "Write a prompt that instructs the AI to outline clear project goals and generate a business proposal—including key objectives and strategic approaches."},
    {"id": 15, "prompt_text": "Take an intentionally vague prompt and rewrite it to be clear, specific, and actionable. Compare the AI’s outputs before and after refinement."},
    {"id": 16, "prompt_text": "Develop a prompt that asks the AI to list the advantages and disadvantages (pros and cons) of a given business decision."},
    {"id": 17, "prompt_text": "Craft a prompt that directs the AI to extract key performance metrics from raw data and highlight the most important KPIs."},
    {"id": 18, "prompt_text": "Design a multi‑step prompt that guides the AI through a sequential process where each step builds on the previous one to solve a problem."},
    {"id": 19, "prompt_text": "Write a prompt that asks the AI to generate creative content—such as advertising slogans, taglines, or short catchphrases—for a product or campaign."},
    {"id": 20, "prompt_text": "Create a prompt that can be adapted by changing contextual details and instruct the AI to generate outputs in various tones (e.g., formal, friendly, humorous)."},
    {"id": 21, "prompt_text": "Craft a prompt that directs the AI to produce a set of frequently asked questions (FAQs) for an internal process and to design a customer feedback survey."},
    {"id": 22, "prompt_text": "Develop two versions of a prompt—one that includes explicit examples and one that doesn’t—and add negative constraints to steer the AI away from unwanted outputs. Compare the differences."},
    {"id": 23, "prompt_text": "Write a prompt that instructs the AI to generate a structured outline for a training session and a detailed, step‑by‑step onboarding guide for new hires."},
    {"id": 24, "prompt_text": "Create a prompt that asks the AI to transform a set of bullet points into a cohesive, flowing narrative paragraph."},
    {"id": 25, "prompt_text": "Formulate a prompt that leverages “if‑then” conditional logic to generate different outputs based on varying scenarios."},
    {"id": 26, "prompt_text": "Craft a prompt that instructs the AI to generate a variety of creative brainstorming ideas for a new marketing campaign."},
    {"id": 27, "prompt_text": "Develop a prompt that asks the AI to produce a set of insightful interview questions tailored for a new role."},
    {"id": 28, "prompt_text": "Design a prompt that initiates a multi‑turn conversation simulating a customer support interaction, ensuring coherent follow‑up responses."},
    {"id": 29, "prompt_text": "Write a prompt that encourages the AI to explain its reasoning step‑by‑step while solving a complex technical problem."},
    {"id": 30, "prompt_text": "Create a prompt that instructs the AI to generate a complete report from raw data—including summaries and visualizations such as charts."},
    {"id": 31, "prompt_text": "Develop a prompt that directs the AI to assume a specific role (for example, a project manager or consultant) and respond as that persona in a simulated scenario."},
    {"id": 32, "prompt_text": "Write a prompt that guides the AI to conduct a brainstorming session for product innovation and then generate a strategic roadmap for product development."},
    {"id": 33, "prompt_text": "Craft a prompt that instructs the AI to develop a full‑scale project proposal complete with detailed timelines, resource allocation, and key milestones."},
    {"id": 34, "prompt_text": "Create a prompt that asks the AI to translate complex technical documentation or industry jargon into clear, accessible language."},
    {"id": 35, "prompt_text": "Develop a prompt that instructs the AI to propose multiple alternative strategies for solving a specific business challenge."},
    {"id": 36, "prompt_text": "Write a multi‑step prompt that guides the AI to integrate financial data for forecasting purposes and to analyze company data to predict future sales trends."},
    {"id": 37, "prompt_text": "Design a series of interconnected prompts where the output of one prompt serves as the input for the next, forming a complete workflow for a complex task."},
    {"id": 38, "prompt_text": "Craft a prompt that directs the AI to analyze current market trends and perform a competitor analysis—complete with visual elements like comparison charts."},
    {"id": 39, "prompt_text": "Develop a prompt that simulates a crisis scenario, asks the AI to perform a detailed risk assessment, and then structure a comprehensive business continuity plan."},
    {"id": 40, "prompt_text": "Create a prompt that instructs the AI to design a detailed customer journey map and generate multiple scenario‑based responses for customer service situations."},
    {"id": 41, "prompt_text": "Write a prompt that asks the AI to generate several versions of a sales pitch and, based on provided KPIs, to offer strategic recommendations for improvement."},
    {"id": 42, "prompt_text": "Develop a prompt that guides the AI to outline a comprehensive internal communication strategy for an organization."},
    {"id": 43, "prompt_text": "Craft a prompt that instructs the AI to generate detailed training materials for new hires, develop a complete digital marketing strategy, and outline a plan for digital transformation initiatives (including an AI adoption training roadmap)."},
    {"id": 44, "prompt_text": "Write a prompt that simulates both a negotiation dialogue for contract discussions and a strategic leadership roundtable discussion or decision‑making scenario."},
    {"id": 45, "prompt_text": "Develop a prompt that instructs the AI to perform a comparative analysis between multiple items, ideas, or strategies."},
    {"id": 46, "prompt_text": "Craft a prompt that directs the AI to conduct a detailed SWOT analysis and synthesize industry research into actionable insights—possibly culminating in an executive briefing on emerging trends."},
    {"id": 47, "prompt_text": "Create a prompt tailored for departments by instructing the AI to generate candidate screening questions for HR and analyze budget reports for the finance team."},
    {"id": 48, "prompt_text": "Develop a prompt that assists the marketing team in generating creative campaign ideas (including a multi‑month marketing calendar) and supports the IT department in diagnosing common system issues."},
    {"id": 49, "prompt_text": "Write a prompt that simulates interdepartmental project planning and instructs the AI to synthesize cross‑departmental feedback into a unified action plan."},
    {"id": 50, "prompt_text": "Craft a prompt that directs the AI to generate detailed customer personas from survey data and to create customized training content for different teams."},
    {"id": 51, "prompt_text": "Develop a prompt that asks the AI to produce a detailed compliance checklist for regulatory requirements and to generate performance review templates for managers."},
    {"id": 52, "prompt_text": "Write a prompt that instructs the AI to identify potential solutions for process bottlenecks and to generate a detailed diagram of an operational workflow."},
    {"id": 53, "prompt_text": "Create a prompt that guides the AI to draft a press release or public communication and to develop a customized crisis communication plan."},
    {"id": 54, "prompt_text": "Develop a prompt that directs the AI to analyze customer data to produce actionable insights and to generate innovative strategies for improving customer retention."},
    {"id": 55, "prompt_text": "Write a capstone prompt that instructs the AI to produce a comprehensive market entry strategy for a new product or service and to design a full‑scale, multi‑phase project plan covering planning, execution, and review."},
    {"id": 56, "prompt_text": "Craft a prompt that asks the AI to develop an executive-level briefing that outlines digital transformation initiatives, including a strategic plan and detailed project timelines."}
]

# State Management (Use Flask's session in a real app!)
current_type = "question"  # Start with a question.  'question' or 'prompt'
question_index = 0
prompt_index = 0

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_next', methods=['GET'])
def get_next():
    global current_type, question_index, prompt_index

    if current_type == "question":
        if question_index < len(questions):
            question = questions[question_index]
            question_index += 1
            current_type = "prompt"  # Switch to prompt after question
            return jsonify({"success": True, "type": "question", "data": question})
        else:
            return jsonify({"success": False, "message": "No more questions."})
    else:  # current_type == "prompt"
        if prompt_index < len(prompts):
            prompt = prompts[prompt_index]
            prompt_index += 1
            current_type = "question"  # Switch to question after prompt
            # Return only the prompt_text, not the entire prompt object
            return jsonify({"success": True, "type": "prompt", "data": {"prompt": prompt["prompt_text"], "id": prompt["id"]}})  # Send prompt text directly
        else:
            return jsonify({"success": False, "message": "No more prompts."})

@app.route('/get_previous', methods=['GET'])
def get_previous():
    global current_type, question_index, prompt_index

    if current_type == "prompt":
        if question_index > 0:
            question_index -= 1
            current_type = "question"
            question = questions[question_index]
            return jsonify({"success": True, "type": "question", "data": question})
        else:
            return jsonify({"success": False, "message": "No previous question."})
    else:  # current_type == "question"
        if prompt_index > 0:
            prompt_index -= 1
            current_type = "prompt"
            prompt = prompts[prompt_index-1] # Adjust index because it was already incremented in get_next
            return jsonify({"success": True, "type": "prompt", "data": {"prompt": prompt["prompt_text"], "id": prompt["id"]}})
        else:
            return jsonify({"success": False, "message": "No previous prompt."})
          


@app.route('/get_all_questions', methods=['GET'])
def get_all_questions():
    """Return all questions for building the sidebar curriculum."""
    return jsonify({"success": True, "questions": questions})

@app.route('/tutor', methods=['POST'])
def tutor():
    data = request.get_json()
    conversation = data.get("conversation", [])

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=conversation
        )
        answer = response.choices[0].message.content
        formatted_answer = markdown.markdown(answer)
    except Exception as e:
        formatted_answer = f"<p>Error: {str(e)}</p>"
        app.logger.error("LLM API error: %s", e)

    return jsonify({"success": True, "answer": formatted_answer})

@app.route('/generate_from_prompt', methods=['POST'])
def generate_from_prompt():
    data = request.get_json()
    user_prompt = data.get("prompt", "")  # Get the prompt text
    is_advanced = data.get("advanced", False)  # Check if advanced prompt is requested

    # VERY IMPORTANT:  Sanitize user_prompt in a real application!
    if not user_prompt:
        return jsonify({"success": False, "message": "Prompt cannot be empty."})

    # Modify the prompt based on the requested type
    if is_advanced:
        modified_prompt = (
            "Please generate an expert level, easy-to-understand and use prompt for a expert in AI. "
            "dont tell user how to create the prompt, create the prompt ready to use"
            "only return the generated prompt with no headings, introductions or explaintions"
            

            f"{user_prompt}"
        )
    else:
        modified_prompt = (
        "Please generate a simple, easy-to-understand and use prompt for a beginner in AI. "
        "dont tell user how to create the prompt, create the prompt ready to use"
        "only return the generated prompt with no introductions or explaintions"
        f"{user_prompt}"
        )

    try:
        # We're already giving the LLM the prompt directly, so no need to wrap it
        response = openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": modified_prompt}]
        )
        answer = response.choices[0].message.content
        formatted_answer = markdown.markdown(answer)
    except Exception as e:
        formatted_answer = f"<p>Error: {str(e)}</p>"
        app.logger.error("LLM API error: %s", e)

    return jsonify({"success": True, "answer": formatted_answer})

# Serve Static Files (CSS and JS)
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
