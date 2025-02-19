// /flask_lms-master/static/js/script2.js
let questions = [];
let prompts = [];
let chatHistory = [];
let currentQuestionData = null;
let currentPromptData = null;
let currentDay = 1;
const totalDays = 50;
let currentPart = "question";

function safeMarkdown(text) {
    if (typeof marked !== 'undefined') {
        return marked.parse(text);
    } else {
        console.warn("Markdown library 'marked' is not available. Rendering plain text.");
        return text;
    }
}

function initializeSidebar() {
    document.body.classList.add('sidebar-hidden');

    const toggleBtn = document.getElementById("toggle-sidebar-btn");
    const sidebar = document.getElementById('curriculum-sidebar');
    const containerFluid = document.querySelector('.container-fluid');

    if (toggleBtn) {
        toggleBtn.addEventListener("click", function(e) {
            e.stopPropagation();
            if (document.body.classList.contains('sidebar-hidden')) {
                document.body.classList.remove('sidebar-hidden');
                if (sidebar && containerFluid) {
                    const sidebarWidth = window.getComputedStyle(sidebar).width || "300px";
                    containerFluid.style.marginLeft = sidebarWidth;
                    containerFluid.style.width = `calc(100% - ${sidebarWidth})`;
                }
            } else {
                document.body.classList.add('sidebar-hidden');
                if (containerFluid) {
                    containerFluid.style.marginLeft = "0";
                    containerFluid.style.width = "100%";
                }
            }
        });
    }

    document.addEventListener('click', function(e) {
        if (!document.body.classList.contains('sidebar-hidden') &&
            sidebar && !sidebar.contains(e.target) &&
            toggleBtn && !toggleBtn.contains(e.target)) {
            document.body.classList.add('sidebar-hidden');
            if (containerFluid) {
                containerFluid.style.marginLeft = "0";
                containerFluid.style.width = "100%";
            }
        }
    });

    document.addEventListener('touchmove', function(e) {
        if (!document.body.classList.contains('sidebar-hidden')) {
            if (!sidebar.contains(e.target)) {
                e.preventDefault();
            }
        }
    }, { passive: false });

    if (sidebar) {
        sidebar.addEventListener('wheel', function(e) {
            e.stopPropagation();
        });

        sidebar.addEventListener('touchstart', function(e) {
            e.stopPropagation();
        });
    }

    window.addEventListener('resize', function() {
        if (!document.body.classList.contains('sidebar-hidden') && sidebar && containerFluid) {
            const sidebarWidth = window.getComputedStyle(sidebar).width || "300px";
            containerFluid.style.marginLeft = sidebarWidth;
            containerFluid.style.width = `calc(100% - ${sidebarWidth})`;
        } else if (containerFluid) {
            containerFluid.style.marginLeft = "0";
            containerFluid.style.width = "100%";
        }
    });
}

document.addEventListener("DOMContentLoaded", function() {
    document.body.classList.add('student-dashboard');
    initializeSidebar();
    loadQuestions();
});

async function loadQuestions() {
    try {
        const [questionData, progressData, promptData] = await Promise.all([
            fetch('/get_all_questions').then(response => response.json()),
            fetch('/get_progress').then(response => response.json()),
            fetch('/get_all_prompts').then(response => response.json())
        ]);

        if (questionData.success && promptData.success) {
            questions = questionData.questions;
            prompts = promptData.prompts;

            currentQuestionData = questions[0];
            currentPromptData = currentQuestionData
                ? prompts.find(p => p.id === currentQuestionData.id) || prompts[0]
                : null;

            const completedQuestions = new Set();
            const completedPrompts = new Set();
            let lastCompletedDay = 1;

            if (progressData.success) {
                progressData.questions_completed?.forEach(id => {
                    completedQuestions.add(id);
                    const question = questions.find(q => q.id === id);
                    if (question) {
                        const dayIndex = questions.indexOf(question) + 1;
                        lastCompletedDay = Math.max(lastCompletedDay, dayIndex);
                    }
                });
                progressData.prompts_completed?.forEach(id => completedPrompts.add(id));

                currentDay = lastCompletedDay;
                if (currentDay > totalDays) currentDay = totalDays;
            } else {
                currentDay = 1;
            }

            populateQuestionList(completedQuestions, completedPrompts);
            currentPart = "question";
            displayQuestion(currentQuestionData);
            document.getElementById("ask-btn").innerText = "Ask";
            document.getElementById("paste-btn").innerText = "Paste Question";
            updatePagination();

            document.getElementById("prompt-task-container").style.display = "none";
            document.getElementById("question-container").style.display = "block";

            const firstItem = document.querySelector('.question-item');
            if (firstItem) {
                firstItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    } catch (error) {
        console.error('Error loading questions:', error);
    }
}

function updatePagination() {
    const pagination = document.getElementById("pagination");
    if (pagination) {
        pagination.innerText = `Day ${currentDay}/${totalDays}`;
    }
}

function updateCurrentDayUI(day) {
    const allItems = document.querySelectorAll('.question-item');
    allItems.forEach(item => item.classList.remove('current'));

    if (day > 0 && day <= allItems.length) {
        const currItem = allItems[day - 1];
        if (currItem) {
            currItem.classList.add('current');
            currItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
}

function populateQuestionList(completedQuestions, completedPrompts) {
    const questionList = document.getElementById("question-list");
    if (!questionList) return;

    questionList.innerHTML = "";
    let currentCategory = null;
    let categoryDiv = null;

    questions.forEach((q, index) => {
        if (currentCategory !== q.category) {
            currentCategory = q.category;
            categoryDiv = document.createElement("div");
            categoryDiv.classList.add("curriculum-category");

            let categoryHeader = document.createElement("h4");
            categoryHeader.innerText = currentCategory;
            categoryDiv.appendChild(categoryHeader);

            questionList.appendChild(categoryDiv);
        }

        let li = document.createElement("div");
        li.classList.add("question-item");

        let questionText = document.createElement("span");
        questionText.classList.add("question-text");
        questionText.innerText = `${index + 1}. ${q.question}`;

        let indicators = document.createElement("span");
        indicators.classList.add("completion-indicators");

        let questionDot = document.createElement("span");
        const isQuestionComplete = completedQuestions.has(q.id);
        questionDot.classList.add("dot", isQuestionComplete ? "completed" : "incomplete");
        questionDot.title = isQuestionComplete ? "✓ Question Completed" : "❌ Question Incomplete";

        let promptDot = document.createElement("span");
        const isPromptComplete = completedPrompts.has(q.id);
        promptDot.classList.add("dot", isPromptComplete ? "completed" : "incomplete");
        promptDot.title = isPromptComplete ? "✓ Prompt Completed" : "❌ Prompt Incomplete";

        let status = "Not started";
        if (isQuestionComplete && isPromptComplete) {
            status = "✓ Day Completed";
        } else if (isQuestionComplete) {
            status = "▶ Prompt Task Pending";
        } else if (index + 1 === currentDay) {
            status = "▶ Current Day";
        }
        li.setAttribute("data-status", status);

        if (index + 1 === currentDay) {
            li.classList.add("current");
        }

        indicators.appendChild(questionDot);
        indicators.appendChild(promptDot);

        li.appendChild(questionText);
        li.appendChild(indicators);
        li.onclick = () => loadSpecificDay(index + 1);

        categoryDiv.appendChild(li);
    });
}

function loadSpecificDay(day) {
    currentDay = day;
    currentPart = "question";

    document.getElementById("user-question").value = "";
    clearChatWindow();
    chatHistory = [];

    const questionData = questions[day - 1];
    const promptData = questionData ? prompts.find(p => p.id === questionData.id) : null;

    if (questionData) {
        currentQuestionData = questionData;
        currentPromptData = promptData;

        document.getElementById("question-container").style.display = "block";
        document.getElementById("prompt-task-container").style.display = "none";

        displayQuestion(questionData);
        document.getElementById("ask-btn").innerText = "Ask";
        document.getElementById("paste-btn").innerText = "Paste Question";

        updateCurrentDayUI(day);
        updatePagination();
    }
}

function displayQuestion(questionData) {
    if (!questionData) return;

    const questionText = document.getElementById("question-text");
    const optionsContainer = document.getElementById("options-container");
    const feedback = document.getElementById("feedback");

    questionText.innerText = questionData.question;
    optionsContainer.innerHTML = "";
    feedback.innerText = "";

    questionData.options.forEach((option, idx) => {
        const div = document.createElement("div");
        div.classList.add("option");
        div.innerText = option;
        div.onclick = () => checkAnswer(idx, questionData.correct, div);
        optionsContainer.appendChild(div);
    });

    document.getElementById("prompt-task-container").style.display = "none";
    document.getElementById("question-container").style.display = "block";
}

function displayPromptTask(promptData) {
    if (!promptData) return;

    const promptContainer = document.getElementById("prompt-task-container");
    promptContainer.style.display = "block";
    document.getElementById("question-container").style.display = "none";

    document.getElementById("prompt-task-text").innerText = promptData.prompt_text;
    document.getElementById("small-chat-input").value = promptData.prompt_text;
    document.getElementById("small-chat-response").innerText = "";

    // Update the department display
    const promptTitle = document.querySelector(".prompt-task-title");
    if (promptTitle) {
        promptTitle.innerText = `Prompt Task - ${promptData.department || 'No Department'}`;
    }
}

function checkAnswer(selectedIndex, correctIndex, element) {
    const feedbackEl = document.getElementById("feedback");
    const options = document.querySelectorAll('.option');

    if (selectedIndex === correctIndex) {
        element.classList.add("correct");
        feedbackEl.innerText = "Correct! Loading prompt task...";
        feedbackEl.style.color = "#28a745";

        options.forEach(opt => opt.style.pointerEvents = 'none');

        fetch("/submit_answer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question_id: currentQuestionData.id,
                selected_answer: selectedIndex,
                is_correct: true
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const allQuestions = document.querySelectorAll('.question-item');
                const currItem = allQuestions[currentDay - 1];
                if (currItem) {
                    const dots = currItem.querySelector('.completion-indicators').children;
                    dots[0].classList.remove('incomplete');
                    dots[0].classList.add('completed');
                    currItem.setAttribute('data-status', '▶ Prompt Task Pending');
                }

                setTimeout(() => {
                    clearChatWindow();
                    chatHistory = [];
                    currentPart = "prompt";
                    const promptData = currentQuestionData
                        ? prompts.find(p => p.id === currentQuestionData.id)
                        : null;

                    if (promptData) {
                        displayPromptTask(promptData);
                    }
                    document.getElementById("ask-btn").innerText = "Generate";
                    document.getElementById("paste-btn").innerText = "Copy Prompt";
                }, 1500);
            }
        })
        .catch(error => console.error('Error:', error));
    } else {
        element.classList.add("incorrect");
        feedbackEl.innerText = "Incorrect. Try again.";
        feedbackEl.style.color = "#dc3545";

        fetch("/submit_answer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question_id: currentQuestionData.id,
                selected_answer: selectedIndex,
                is_correct: false
            })
        });
    }
}

async function loadNext() {
    document.getElementById("user-question").value = "";
    clearChatWindow();
    chatHistory = [];

    if (currentPart === "question") {
        currentPart = "prompt";
        const promptData = prompts[currentDay - 1];
        if (promptData) {
            displayPromptTask(promptData);
            document.getElementById("ask-btn").innerText = "Generate";
            document.getElementById("paste-btn").innerText = "Copy Prompt";
        }
    } else if (currentPart === "prompt") {
        currentDay++;
        if (currentDay > totalDays) currentDay = totalDays;
        const questionData = questions[currentDay - 1];
        const promptData = prompts[currentDay - 1];
        if (questionData) {
            currentQuestionData = questionData;
            currentPromptData = promptData;
            currentPart = "question";
            document.getElementById("question-container").style.display = "block";
            document.getElementById("prompt-task-container").style.display = "none";
            displayQuestion(questionData);
            document.getElementById("ask-btn").innerText = "Ask";
            document.getElementById("paste-btn").innerText = "Paste Question";
        }
    }

    updatePagination();
    updateCurrentDayUI(currentDay);
}

async function loadPrevious() {
    document.getElementById("user-question").value = "";
    clearChatWindow();
    chatHistory = [];

    if (currentPart === "prompt") {
        currentPart = "question";
        const questionData = questions[currentDay - 1];
        if (questionData) {
            document.getElementById("question-container").style.display = "block";
            document.getElementById("prompt-task-container").style.display = "none";
            displayQuestion(questionData);
            document.getElementById("ask-btn").innerText = "Ask";
            document.getElementById("paste-btn").innerText = "Paste Question";
        }
    } else if (currentPart === "question") {
        if (currentDay > 1) {
            currentDay--;
            const questionData = questions[currentDay - 1];
            const promptData = prompts[currentDay - 1];
            if (questionData) {
                currentQuestionData = questionData;
                currentPromptData = promptData;
                currentPart = "prompt";
                document.getElementById("question-container").style.display = "none";
                document.getElementById("prompt-task-container").style.display = "block";
                displayPromptTask(promptData);
                document.getElementById("ask-btn").innerText = "Generate";
                document.getElementById("paste-btn").innerText = "Copy Prompt";
            }
        }
    }

    updatePagination();
    updateCurrentDayUI(currentDay);
}

function clearChatWindow() {
    const chatWindow = document.getElementById("chat-window");
    chatWindow.innerHTML = "";
    chatHistory = [];
}

function clearTutor() {
    clearChatWindow();
    document.getElementById("user-question").value = "";
}

function generateFromSmallChat(isAdvanced) {
    const prompt = document.getElementById("small-chat-input").value;
    if (!prompt) return;

    fetch("/generate_from_prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt, advanced: isAdvanced })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById("small-chat-response").innerHTML = safeMarkdown(data.answer);

            fetch("/submit_prompt_response", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    prompt_id: currentPromptData.id,
                    response: data.answer
                })
            })
            .then(response => response.json())
            .then(submitData => {
                if (submitData.success) {
                    const allQuestions = document.querySelectorAll('.question-item');
                    const currItem = allQuestions[currentDay - 1];
                    if (currItem) {
                        const dots = currItem.querySelector('.completion-indicators').children;
                        dots[1].classList.remove('incomplete');
                        dots[1].classList.add('completed');
                        currItem.setAttribute('data-status', '✓ Day Completed');
                    }
                }
            });
        }
    });
}

function askTutor() {
    const userInput = document.getElementById("user-question").value.trim();
    if (!userInput) return;

    appendChatBubble("user", userInput);
    chatHistory.push({ role: "user", content: userInput });
    document.getElementById("user-question").value = "";

    fetch("/tutor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversation: chatHistory, prompt_id: currentPromptData ? currentPromptData.id : null })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            appendChatBubble("assistant", data.answer);
            chatHistory.push({ role: "assistant", content: data.answer });
        }
    });
}
//modified to fix the alignment
function appendChatBubble(sender, text) {
    const chatWindow = document.getElementById("chat-window");
    const bubble = document.createElement("div");
    bubble.classList.add("chat-bubble"); // Add the base class

    if (sender === "user") {
        bubble.classList.add("user-bubble"); // Add user-specific class
    } else {
        bubble.classList.add("tutor-bubble"); // Add tutor-specific class
    }

    bubble.innerHTML = safeMarkdown(text);
    chatWindow.appendChild(bubble);
    chatWindow.scrollTop = chatWindow.scrollHeight; // Auto-scroll
}

function pasteQuestion() {
    if (currentPart === "prompt") {
        document.getElementById("user-question").value = document.getElementById("small-chat-response").innerText;
    } else {
        document.getElementById("user-question").value = document.getElementById("question-text").innerText;
    }
}

function copyChat() {
    const chatWindow = document.getElementById("chat-window");
    navigator.clipboard.writeText(chatWindow.innerText)
        .then(() => alert("Chat copied to clipboard"))
        .catch(err => console.error('Failed to copy:', err));
}
