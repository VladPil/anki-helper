"""Sample test data for AnkiRAG backend tests.

This module provides consistent sample data for testing various
components of the application.

Usage:
    from tests.fixtures.sample_data import SAMPLE_USER_DATA, SAMPLE_CARDS

    # Use in tests
    response = await client.post("/auth/register", json=SAMPLE_USER_DATA["valid"])
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

# ==================== User Data ====================


SAMPLE_USER_DATA: dict[str, dict[str, Any]] = {
    "valid": {
        "email": "newuser@example.com",
        "display_name": "New User",
        "password": "SecurePassword123!",
    },
    "valid_alt": {
        "email": "altuser@example.com",
        "display_name": "Alt User",
        "password": "AnotherPassword456!",
    },
    "invalid_email": {
        "email": "not-an-email",
        "display_name": "Invalid Email User",
        "password": "SecurePassword123!",
    },
    "short_password": {
        "email": "shortpass@example.com",
        "display_name": "Short Password User",
        "password": "short",
    },
    "empty_display_name": {
        "email": "empty@example.com",
        "display_name": "",
        "password": "SecurePassword123!",
    },
    "unicode_display_name": {
        "email": "unicode@example.com",
        "display_name": "Unicode User",
        "password": "SecurePassword123!",
    },
    "long_display_name": {
        "email": "long@example.com",
        "display_name": "A" * 150,  # Exceeds 100 char limit
        "password": "SecurePassword123!",
    },
    "special_chars_email": {
        "email": "user+tag@example.com",
        "display_name": "Tagged User",
        "password": "SecurePassword123!",
    },
}

SAMPLE_LOGIN_DATA: dict[str, dict[str, str]] = {
    "valid": {
        "email": "test@example.com",
        "password": "testpassword123",
    },
    "wrong_password": {
        "email": "test@example.com",
        "password": "wrongpassword",
    },
    "nonexistent_user": {
        "email": "nonexistent@example.com",
        "password": "somepassword",
    },
}


# ==================== Deck Data ====================


SAMPLE_DECK_DATA: dict[str, dict[str, Any]] = {
    "basic": {
        "name": "Japanese Vocabulary",
        "description": "Common Japanese words and phrases for beginners",
    },
    "no_description": {
        "name": "Quick Notes",
        "description": None,
    },
    "nested_parent": {
        "name": "Languages",
        "description": "Parent deck for all language learning decks",
    },
    "nested_child": {
        "name": "Japanese::Vocabulary",
        "description": "Japanese vocabulary subdeck",
    },
    "long_name": {
        "name": "A" * 300,  # Exceeds 255 char limit
        "description": "Invalid deck name",
    },
    "empty_name": {
        "name": "",
        "description": "Invalid empty name",
    },
    "special_chars": {
        "name": "Deck with 'quotes' and \"double quotes\"",
        "description": "Testing special characters",
    },
    "unicode": {
        "name": "Deck",
        "description": "Deck with Japanese characters",
    },
}


# ==================== Card Data ====================


SAMPLE_CARD_DATA: dict[str, dict[str, Any]] = {
    "basic": {
        "front": "What is the capital of Japan?",
        "back": "Tokyo",
        "tags": ["geography", "japan"],
    },
    "cloze": {
        "text": "The capital of {{c1::Japan}} is {{c2::Tokyo}}.",
        "extra": "Japan is an island country in East Asia.",
        "tags": ["geography", "cloze"],
    },
    "with_media": {
        "front": "What animal is shown in the image?",
        "back": "A cat",
        "image_url": "https://example.com/cat.jpg",
        "tags": ["animals", "images"],
    },
    "japanese": {
        "front": "(konnichiwa) - what does this mean?",
        "back": "Hello / Good afternoon",
        "reading": "konnichiwa",
        "tags": ["japanese", "greetings"],
    },
    "empty_front": {
        "front": "",
        "back": "Some answer",
        "tags": [],
    },
    "empty_back": {
        "front": "Some question",
        "back": "",
        "tags": [],
    },
    "long_content": {
        "front": "A" * 10000,
        "back": "B" * 10000,
        "tags": ["long"],
    },
}


# ==================== Template Data ====================


SAMPLE_TEMPLATE_DATA: dict[str, dict[str, Any]] = {
    "basic": {
        "name": "basic",
        "display_name": "Basic",
        "fields_schema": {
            "type": "object",
            "properties": {
                "front": {"type": "string", "description": "Question or prompt"},
                "back": {"type": "string", "description": "Answer"},
            },
            "required": ["front", "back"],
        },
        "front_template": "<div class='front'>{{front}}</div>",
        "back_template": "<div class='back'>{{FrontSide}}<hr>{{back}}</div>",
        "css": ".front { font-size: 20px; text-align: center; }",
    },
    "cloze": {
        "name": "cloze",
        "display_name": "Cloze Deletion",
        "fields_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text with cloze deletions"},
                "extra": {"type": "string", "description": "Extra information"},
            },
            "required": ["text"],
        },
        "front_template": "{{cloze:text}}",
        "back_template": "{{cloze:text}}<br><br>{{extra}}",
        "css": ".cloze { font-weight: bold; color: blue; }",
    },
    "vocabulary": {
        "name": "vocabulary",
        "display_name": "Vocabulary Card",
        "fields_schema": {
            "type": "object",
            "properties": {
                "word": {"type": "string"},
                "reading": {"type": "string"},
                "meaning": {"type": "string"},
                "example": {"type": "string"},
            },
            "required": ["word", "meaning"],
        },
        "front_template": "<div class='word'>{{word}}</div><div class='reading'>{{reading}}</div>",
        "back_template": "{{FrontSide}}<hr><div class='meaning'>{{meaning}}</div><div class='example'>{{example}}</div>",
        "css": ".word { font-size: 32px; } .reading { font-size: 18px; color: gray; }",
    },
    "invalid_schema": {
        "name": "invalid",
        "display_name": "Invalid Schema",
        "fields_schema": "not a valid schema",  # Invalid
        "front_template": "{{front}}",
        "back_template": "{{back}}",
    },
    "empty_templates": {
        "name": "empty",
        "display_name": "Empty Templates",
        "fields_schema": {"type": "object", "properties": {}},
        "front_template": "",
        "back_template": "",
    },
}


# ==================== Chat Data ====================


SAMPLE_CHAT_SESSION_DATA: dict[str, dict[str, Any]] = {
    "basic": {
        "title": "Learning Japanese",
        "context": None,
    },
    "with_deck_context": {
        "title": "Vocabulary Practice",
        "context": {
            "deck_id": "00000000-0000-0000-0000-000000000001",
            "topic": "Japanese vocabulary",
        },
    },
    "with_topic_context": {
        "title": "Grammar Questions",
        "context": {
            "topic": "Japanese grammar",
            "level": "beginner",
        },
    },
    "empty_title": {
        "title": "",
        "context": None,
    },
    "long_title": {
        "title": "A" * 300,
        "context": None,
    },
}

SAMPLE_CHAT_MESSAGES: dict[str, dict[str, Any]] = {
    "user_question": {
        "content": "What is the difference between wa and ga particles?",
        "role": "user",
    },
    "assistant_response": {
        "content": "The particles wa and ga have distinct uses in Japanese...",
        "role": "assistant",
    },
    "system_prompt": {
        "content": "You are a helpful Japanese language tutor.",
        "role": "system",
    },
    "empty_content": {
        "content": "",
        "role": "user",
    },
    "long_content": {
        "content": "A" * 15000,  # Exceeds 10000 char limit
        "role": "user",
    },
    "with_context_query": {
        "content": "Explain the particle wa",
        "context_query": "Japanese particle wa topic marker",
        "role": "user",
    },
}


# ==================== RAG Data ====================


SAMPLE_DOCUMENTS: list[dict[str, Any]] = [
    {
        "content": "The Japanese particle 'wa' is used to mark the topic of a sentence. "
                   "It indicates what the sentence is about.",
        "metadata": {
            "source": "japanese_grammar_guide.pdf",
            "page": 15,
            "topic": "particles",
        },
    },
    {
        "content": "The particle 'ga' is used to mark the subject of a sentence, "
                   "especially in neutral descriptions or when introducing new information.",
        "metadata": {
            "source": "japanese_grammar_guide.pdf",
            "page": 16,
            "topic": "particles",
        },
    },
    {
        "content": "Anki uses spaced repetition to help you remember information more efficiently. "
                   "Cards are shown at increasing intervals as you learn them.",
        "metadata": {
            "source": "anki_manual.pdf",
            "page": 1,
            "topic": "introduction",
        },
    },
    {
        "content": "Cloze deletion cards are useful for memorizing facts by hiding key information. "
                   "Use {{c1::text}} syntax to create cloze deletions.",
        "metadata": {
            "source": "anki_manual.pdf",
            "page": 25,
            "topic": "card_types",
        },
    },
]

SAMPLE_EMBEDDINGS: list[list[float]] = [
    [0.1, 0.2, 0.3] * 512,  # 1536 dimensions (OpenAI)
    [0.4, 0.5, 0.6] * 512,
    [0.7, 0.8, 0.9] * 512,
    [0.2, 0.3, 0.4] * 512,
]


# ==================== Generation Data ====================


SAMPLE_GENERATION_REQUESTS: dict[str, dict[str, Any]] = {
    "basic_card": {
        "topic": "Japanese particle 'wa'",
        "card_type": "basic",
        "num_cards": 3,
        "language": "en",
    },
    "cloze_card": {
        "topic": "Japanese verb conjugation",
        "card_type": "cloze",
        "num_cards": 5,
        "language": "en",
    },
    "with_context": {
        "topic": "Japanese greetings",
        "card_type": "basic",
        "num_cards": 3,
        "context": "Focus on formal and informal variations",
        "language": "ja",
    },
    "invalid_card_type": {
        "topic": "Test",
        "card_type": "invalid_type",
        "num_cards": 1,
    },
    "too_many_cards": {
        "topic": "Test",
        "card_type": "basic",
        "num_cards": 1000,  # Exceeds limit
    },
}

SAMPLE_GENERATED_CARDS: list[dict[str, Any]] = [
    {
        "front": "What particle marks the topic of a Japanese sentence?",
        "back": "wa",
        "tags": ["japanese", "particles", "grammar"],
    },
    {
        "front": "In the sentence 'Watashi wa gakusei desu', what does 'wa' indicate?",
        "back": "'wa' marks 'watashi' (I) as the topic of the sentence",
        "tags": ["japanese", "particles", "grammar"],
    },
    {
        "front": "Can 'wa' be used with objects?",
        "back": "Yes, 'wa' can replace 'wo' to add emphasis or contrast to an object",
        "tags": ["japanese", "particles", "grammar"],
    },
]


# ==================== Prompt Data ====================


SAMPLE_PROMPTS: dict[str, dict[str, Any]] = {
    "card_generation": {
        "template": """Generate {num_cards} flashcards about {topic}.
Each card should have a clear question and answer.
Format: JSON array of objects with 'front' and 'back' fields.
Language: {language}""",
        "variables": {
            "num_cards": 3,
            "topic": "Japanese particles",
            "language": "English",
        },
    },
    "rag_context": {
        "template": """Based on the following context, answer the user's question.

Context:
{context}

Question: {question}

Provide a clear and concise answer.""",
        "variables": {
            "context": "The particle 'wa' marks the topic...",
            "question": "What is the particle 'wa' used for?",
        },
    },
    "missing_variable": {
        "template": "Generate cards about {topic} in {language}",
        "variables": {
            "topic": "Test topic",
            # Missing 'language'
        },
    },
}


# ==================== API Response Data ====================


SAMPLE_API_RESPONSES: dict[str, dict[str, Any]] = {
    "success": {
        "status": "success",
        "message": "Operation completed successfully",
    },
    "error_validation": {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Validation failed",
            "details": [
                {"field": "email", "message": "Invalid email format"},
            ],
        },
    },
    "error_not_found": {
        "error": {
            "code": "NOT_FOUND",
            "message": "Resource not found",
        },
    },
    "error_unauthorized": {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Authentication required",
        },
    },
    "error_forbidden": {
        "error": {
            "code": "FORBIDDEN",
            "message": "Access denied",
        },
    },
}


# ==================== Sync Data ====================


SAMPLE_ANKI_DECKS: list[dict[str, Any]] = [
    {"id": 1, "name": "Default"},
    {"id": 1000001, "name": "Japanese"},
    {"id": 1000002, "name": "Japanese::Vocabulary"},
    {"id": 1000003, "name": "Japanese::Grammar"},
]

SAMPLE_ANKI_NOTES: list[dict[str, Any]] = [
    {
        "id": 1,
        "modelName": "Basic",
        "fields": {
            "Front": "What is wa?",
            "Back": "A topic marker particle",
        },
        "tags": ["japanese", "particles"],
    },
    {
        "id": 2,
        "modelName": "Cloze",
        "fields": {
            "Text": "The particle {{c1::wa}} marks the topic",
            "Extra": "Basic grammar concept",
        },
        "tags": ["japanese", "cloze"],
    },
]


# ==================== Test IDs ====================


TEST_UUIDS: dict[str, UUID] = {
    "user_1": UUID("00000000-0000-0000-0000-000000000001"),
    "user_2": UUID("00000000-0000-0000-0000-000000000002"),
    "deck_1": UUID("00000000-0000-0000-0000-000000000010"),
    "deck_2": UUID("00000000-0000-0000-0000-000000000011"),
    "card_1": UUID("00000000-0000-0000-0000-000000000020"),
    "card_2": UUID("00000000-0000-0000-0000-000000000021"),
    "template_1": UUID("00000000-0000-0000-0000-000000000030"),
    "session_1": UUID("00000000-0000-0000-0000-000000000040"),
    "message_1": UUID("00000000-0000-0000-0000-000000000050"),
    "nonexistent": UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
}


# ==================== Timestamps ====================


SAMPLE_TIMESTAMPS: dict[str, datetime] = {
    "now": datetime.now(UTC),
    "past": datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
    "future": datetime(2030, 12, 31, 23, 59, 59, tzinfo=UTC),
}
