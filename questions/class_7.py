"""
Class 7 — Mystery Island Theme
Question types:
  mcq           → definite answer, scored locally
  tap_wrong_word→ tap the one wrong word in a sentence, scored locally
  fill_blank     → fill one or two blanks from given options, scored locally
  sentence_build → arrange shuffled words into a correct sentence, scored locally
  rewrite        → rewrite an incorrect sentence correctly, scored by Gemini
  open_text      → write a creative / open-ended sentence, scored by Gemini
  speech         → speak a free-form answer, scored by Azure + Gemini
  conversational_writing → chat-based writing with AI feedback and follow-ups
"""

QUESTIONS = [

    # ─── LISTENING ────────────────────────────────────────────────────────────

    {
        "id": 1,
        "section": "listening",
        "type": "mcq",
        "audio_script": "The chest has a star, a moon, and a fish on it.",
        "question": "Sam says: \"The chest has a star, a moon, and a fish on it.\" How many symbols are there?",
        "options": ["2", "3", "4", "5"],
        "answer": "3",
        "feedback_wrong": "Bro counted vibes instead of symbols 😅"
    },

    {
        "id": 2,
        "section": "listening",
        "type": "mcq",
        "audio_script": "The island was silent and ____.",
        "question": "\"The island was silent and ____.\" Which word fits best?",
        "options": ["Noisy", "Mysterious", "Crowded", "Sunny"],
        "answer": "Mysterious",
        "feedback_wrong": "Think about the mood — it was quiet and eerie 🌙"
    },

    {
        "id": 3,
        "section": "listening",
        "type": "mcq",
        "audio_script": "Don't open it until you solve the riddle.",
        "question": "Sam says: \"Don't open it until you solve the riddle.\" What should you do FIRST?",
        "options": ["Open the chest", "Solve the riddle", "Run away", "Call for help"],
        "answer": "Solve the riddle",
        "feedback_wrong": "Khatam. Tata. Bye bye. Good-bye! 👋"
    },

    {
        "id": 4,
        "section": "listening",
        "type": "mcq",
        "audio_script": "The treasure lies where the river meets the roots.",
        "question": "The note says: \"The treasure lies where the river meets the roots.\" Which clue tells you the LOCATION?",
        "options": ["The river", "Where river meets roots", "The roots only", "The treasure"],
        "answer": "Where river meets roots",
        "feedback_wrong": "Read both parts of the clue together 🌊🌳"
    },

    {
        "id": 5,
        "section": "listening",
        "type": "mcq",
        "audio_script": "Before we cross the wobbly bridge, we need to tie this thick rope to the giant tree.",
        "question": "The audio log says: \"Before we cross the wobbly bridge, we need to tie this thick rope to the giant tree.\" What must the explorers do SECOND?",
        "options": ["Find the tree", "Cross the bridge", "Tie the rope", "Cut the rope"],
        "answer": "Cross the bridge",
        "feedback_wrong": "They tie the rope FIRST, then cross 🌉"
    },

    # ─── READING ──────────────────────────────────────────────────────────────

    {
        "id": 6,
        "section": "reading",
        "type": "tap_wrong_word",
        "sentence": "Meera runned to the chest.",
        "question": "Tap the ONE wrong word: \"Meera runned to the chest.\"",
        "answer": "runned",
        "feedback_wrong": "The wrong word is 'runned' — it should be 'ran' 🏃"
    },

    {
        "id": 7,
        "section": "reading",
        "type": "mcq",
        "question": "\"Beware the loose stone.\" What does \"beware\" mean?",
        "options": ["Pick up", "Be careful of", "Ignore", "Step on"],
        "answer": "Be careful of",
        "feedback_wrong": "Beware = watch out / be careful of ⚠️"
    },

    {
        "id": 8,
        "section": "reading",
        "type": "mcq",
        "question": "\"She crept forward, step by careful step.\" What does \"crept\" tell us?",
        "options": ["She moved fast", "She moved quietly and slowly", "She ran", "She jumped"],
        "answer": "She moved quietly and slowly",
        "feedback_wrong": "Creeping means quiet, careful movement 🐱"
    },

    {
        "id": 9,
        "section": "reading",
        "type": "fill_blank",
        "question": "Fill both blanks: \"Meera ___ the map ___ before making her decision.\"",
        "blanks": 2,
        "options": ["Studied", "carefully", "watched", "quickly", "read", "slowly"],
        "answer": ["studied", "carefully"],
        "feedback_wrong": "She studied the map carefully — methodically! 🗺️"
    },

    # ─── WRITING ──────────────────────────────────────────────────────────────
    
    {
        "id": 10,
        "section": "writing",
        "type": "conversational_writing",
        "question": "Describe this image in 1-2 sentences:",
        "image": "kid-sketch.png",
        "image_description": "The image is a drawing by a child. It shows a kid wearing a blue colored t-shirt with a scarf holding a bright balloon, standing near a house and a road. There is a sun, some trees, and clouds in the background. There are flowers in front of the house as well.",
        "initial_message": "Hey! Look at this cool drawing! Can you describe what you see in 1-2 sentences?",
        "hint": "What do you see in the sketch? Maybe describe the kid, the house, or the weather!",
        "feedback_wrong": None
    },

    {
        "id": 11,
        "section": "writing",
        "type": "sentence_build",
        "question": "Build the sentence — tap words in the correct order:",
        "words": ["The", "ancient", "chest", "was", "buried", "beneath", "the", "roots"],
        "answer": "The ancient chest was buried beneath the roots",
        "feedback_wrong": "The correct order: The ancient chest was buried beneath the roots 📜"
    },

    {
        "id": 12,
        "section": "writing",
        "type": "mcq",
        "question": "The scroll uses picture-words (🌊🌲🏔️). What does this mean?",
        "options": [
            "Walk towards the tree near the water",
            "Swim to the forest",
            "The water is behind the tree",
            "Run from the waves"
        ],
        "answer": "Walk towards the tree near the water",
        "feedback_wrong": "Water → tree → mountain = walk towards tree near water 🗺️"
    },

    {
        "id": 13,
        "section": "writing",
        "type": "rewrite",
        "question": "Rewrite this sentence correctly: \"Sam tell Meera to be careful.\"",
        "correct_version": "Sam told Meera to be careful.",
        "feedback_wrong": None   # Gemini will evaluate
    },
    
  
    {
        "id": 14,
        "section": "writing",
        "type": "fill_blank",
        "question": "Fill the blank: \"She ___ the chest open slowly.\"",
        "blanks": 1,
        "options": ["Opened", "Opens", "Opening"],
        "answer": ["opened"],
        "feedback_wrong": "Past tense needed here — 'opened' ✍️"
    },

    # ─── SPEAKING ─────────────────────────────────────────────────────────────

    {
        "id": 15,
        "section": "speaking",
        "type": "conversational_speech",
        "question": "Hi! I'm Sam. How are you doing today? How was your day?",
        "audio_script": "Hi! I'm Sam. How are you doing today? How was your day?",
        "initial_message": "Hi! I'm Sam. How are you doing today? How was your day?",
        "hint": "Try to answer in 1-2 friendly sentences!",
        "feedback_wrong": None
    },

]