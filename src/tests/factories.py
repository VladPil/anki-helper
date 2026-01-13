"""Factory Boy factories for generating test data.

These factories provide a convenient way to create model instances
for testing with realistic, randomized data.

Usage:
    from tests.factories import UserFactory, DeckFactory

    # Create a user instance (not saved to DB)
    user = UserFactory.build()

    # Create and save a user to the database
    user = await UserFactory.create_async(session=db_session)

    # Create a batch of users
    users = UserFactory.build_batch(10)
"""

import factory
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from factory import LazyAttribute, LazyFunction, Sequence, SubFactory

from src.shared.uuid7 import uuid7
from src.core.security import hash_password
from src.modules.users.models import User, UserPreferences
from src.modules.decks.models import Deck
from src.modules.templates.models import CardTemplate, TemplateField
from src.modules.chat.models import ChatSession, ChatMessage


# ==================== Base Factory ====================


class AsyncSQLAlchemyFactory(factory.Factory):
    """Base factory for async SQLAlchemy models.

    Provides a method to create instances asynchronously with a database session.
    """

    class Meta:
        abstract = True

    @classmethod
    async def create_async(cls, session, **kwargs) -> Any:
        """Create an instance and add it to the database session.

        Args:
            session: Async SQLAlchemy session.
            **kwargs: Override attributes for the factory.

        Returns:
            The created model instance.
        """
        instance = cls.build(**kwargs)
        session.add(instance)
        await session.flush()
        await session.refresh(instance)
        return instance

    @classmethod
    async def create_batch_async(cls, session, size: int, **kwargs) -> list[Any]:
        """Create multiple instances and add them to the database session.

        Args:
            session: Async SQLAlchemy session.
            size: Number of instances to create.
            **kwargs: Override attributes for the factory.

        Returns:
            List of created model instances.
        """
        instances = cls.build_batch(size, **kwargs)
        for instance in instances:
            session.add(instance)
        await session.flush()
        for instance in instances:
            await session.refresh(instance)
        return instances


# ==================== User Factories ====================


class UserFactory(AsyncSQLAlchemyFactory):
    """Factory for creating User instances."""

    class Meta:
        model = User

    id = LazyFunction(uuid7)
    email = Sequence(lambda n: f"user{n}@example.com")
    display_name = Sequence(lambda n: f"Test User {n}")
    hashed_password = LazyFunction(lambda: hash_password("testpassword123"))
    is_active = True
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = LazyFunction(lambda: datetime.now(timezone.utc))
    deleted_at = None

    class Params:
        inactive = factory.Trait(is_active=False)
        deleted = factory.Trait(
            deleted_at=LazyFunction(lambda: datetime.now(timezone.utc))
        )
        with_weak_password = factory.Trait(
            hashed_password=LazyFunction(lambda: hash_password("weak"))
        )


class UserPreferencesFactory(AsyncSQLAlchemyFactory):
    """Factory for creating UserPreferences instances."""

    class Meta:
        model = UserPreferences

    id = LazyFunction(uuid7)
    user_id = None  # Must be set explicitly or via SubFactory
    preferred_language = "en"
    default_model_id = None
    default_embedder_id = None
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = LazyFunction(lambda: datetime.now(timezone.utc))

    class Params:
        russian = factory.Trait(preferred_language="ru")
        spanish = factory.Trait(preferred_language="es")


# ==================== Deck Factories ====================


class DeckFactory(AsyncSQLAlchemyFactory):
    """Factory for creating Deck instances."""

    class Meta:
        model = Deck

    id = LazyFunction(uuid7)
    name = Sequence(lambda n: f"Test Deck {n}")
    description = LazyAttribute(lambda obj: f"Description for {obj.name}")
    owner_id = None  # Must be set explicitly
    parent_id = None
    anki_deck_id = None
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = LazyFunction(lambda: datetime.now(timezone.utc))
    deleted_at = None
    created_by = None
    updated_by = None

    class Params:
        deleted = factory.Trait(
            deleted_at=LazyFunction(lambda: datetime.now(timezone.utc))
        )
        synced = factory.Trait(
            anki_deck_id=Sequence(lambda n: 1000000 + n)
        )
        no_description = factory.Trait(description=None)


class NestedDeckFactory(DeckFactory):
    """Factory for creating nested Deck instances with parent."""

    parent_id = None  # Must be set explicitly


# ==================== Template Factories ====================


class CardTemplateFactory(AsyncSQLAlchemyFactory):
    """Factory for creating CardTemplate instances."""

    class Meta:
        model = CardTemplate

    id = LazyFunction(uuid7)
    name = Sequence(lambda n: f"template_{n}")
    display_name = Sequence(lambda n: f"Test Template {n}")
    fields_schema = LazyFunction(lambda: {
        "type": "object",
        "properties": {
            "front": {"type": "string"},
            "back": {"type": "string"},
        },
        "required": ["front", "back"],
    })
    front_template = "<div class='front'>{{front}}</div>"
    back_template = "<div class='back'>{{back}}</div>"
    css = ".front { font-size: 20px; } .back { font-size: 16px; }"
    is_system = False
    owner_id = None  # Must be set explicitly

    class Params:
        system = factory.Trait(
            is_system=True,
            owner_id=None,
        )
        cloze = factory.Trait(
            name="cloze",
            display_name="Cloze Deletion",
            fields_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "extra": {"type": "string"},
                },
                "required": ["text"],
            },
            front_template="{{cloze:text}}",
            back_template="{{cloze:text}}<br>{{extra}}",
        )
        basic = factory.Trait(
            name="basic",
            display_name="Basic",
        )
        no_css = factory.Trait(css=None)


class TemplateFieldFactory(AsyncSQLAlchemyFactory):
    """Factory for creating TemplateField instances."""

    class Meta:
        model = TemplateField

    id = LazyFunction(uuid7)
    template_id = None  # Must be set explicitly
    name = Sequence(lambda n: f"field_{n}")
    field_type = "text"
    is_required = True
    order = Sequence(lambda n: n)

    class Params:
        optional = factory.Trait(is_required=False)
        html_field = factory.Trait(field_type="html")
        image_field = factory.Trait(field_type="image")
        audio_field = factory.Trait(field_type="audio")


# ==================== Chat Factories ====================


class ChatSessionFactory(AsyncSQLAlchemyFactory):
    """Factory for creating ChatSession instances."""

    class Meta:
        model = ChatSession

    id = LazyFunction(uuid7)
    user_id = None  # Must be set explicitly
    title = Sequence(lambda n: f"Chat Session {n}")
    context = None
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = LazyFunction(lambda: datetime.now(timezone.utc))

    class Params:
        with_deck_context = factory.Trait(
            context={"deck_id": "00000000-0000-0000-0000-000000000001"}
        )
        with_topic_context = factory.Trait(
            context={"topic": "Japanese Vocabulary"}
        )


class ChatMessageFactory(AsyncSQLAlchemyFactory):
    """Factory for creating ChatMessage instances."""

    class Meta:
        model = ChatMessage

    id = LazyFunction(uuid7)
    session_id = None  # Must be set explicitly
    role = "user"
    content = Sequence(lambda n: f"Test message {n}")
    tokens = None
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = LazyFunction(lambda: datetime.now(timezone.utc))

    class Params:
        assistant = factory.Trait(role="assistant")
        system = factory.Trait(role="system")
        with_tokens = factory.Trait(tokens=Sequence(lambda n: 100 + n))


# ==================== Helper Functions ====================


def create_user_with_preferences_data() -> dict[str, Any]:
    """Generate data for creating a user with preferences."""
    return {
        "email": f"newuser{factory.Faker('random_int')}@example.com",
        "display_name": factory.Faker("name").generate(),
        "password": "SecurePassword123!",
    }


def create_deck_data(owner_id: UUID) -> dict[str, Any]:
    """Generate data for creating a deck."""
    return {
        "name": f"New Deck {factory.Faker('random_int').generate()}",
        "description": factory.Faker("sentence").generate(),
        "owner_id": owner_id,
    }


def create_template_data() -> dict[str, Any]:
    """Generate data for creating a template."""
    return {
        "name": f"template_{factory.Faker('random_int').generate()}",
        "display_name": factory.Faker("sentence").generate(),
        "fields_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "answer": {"type": "string"},
            },
            "required": ["question", "answer"],
        },
        "front_template": "<div>{{question}}</div>",
        "back_template": "<div>{{answer}}</div>",
    }


def create_chat_message_data() -> dict[str, Any]:
    """Generate data for creating a chat message."""
    return {
        "content": factory.Faker("paragraph").generate(),
    }


# ==================== Batch Creation Helpers ====================


async def create_user_with_decks(
    session,
    num_decks: int = 3,
    nested: bool = False,
) -> tuple[User, list[Deck]]:
    """Create a user with multiple decks.

    Args:
        session: Async SQLAlchemy session.
        num_decks: Number of decks to create.
        nested: Whether to create nested deck hierarchy.

    Returns:
        Tuple of (User, list of Decks).
    """
    user = await UserFactory.create_async(session)

    decks = []
    parent_id = None

    for i in range(num_decks):
        deck = await DeckFactory.create_async(
            session,
            owner_id=user.id,
            parent_id=parent_id if nested and i > 0 else None,
        )
        decks.append(deck)
        if nested:
            parent_id = deck.id

    return user, decks


async def create_chat_session_with_messages(
    session,
    user_id: UUID,
    num_messages: int = 5,
) -> tuple[ChatSession, list[ChatMessage]]:
    """Create a chat session with messages.

    Args:
        session: Async SQLAlchemy session.
        user_id: User ID for the session.
        num_messages: Number of messages to create.

    Returns:
        Tuple of (ChatSession, list of ChatMessages).
    """
    chat_session = await ChatSessionFactory.create_async(
        session,
        user_id=user_id,
    )

    messages = []
    for i in range(num_messages):
        role = "user" if i % 2 == 0 else "assistant"
        message = await ChatMessageFactory.create_async(
            session,
            session_id=chat_session.id,
            role=role,
        )
        messages.append(message)

    return chat_session, messages


async def create_template_with_fields(
    session,
    owner_id: UUID | None = None,
    num_fields: int = 3,
    is_system: bool = False,
) -> tuple[CardTemplate, list[TemplateField]]:
    """Create a template with fields.

    Args:
        session: Async SQLAlchemy session.
        owner_id: Owner user ID (None for system templates).
        num_fields: Number of fields to create.
        is_system: Whether this is a system template.

    Returns:
        Tuple of (CardTemplate, list of TemplateFields).
    """
    template = await CardTemplateFactory.create_async(
        session,
        owner_id=owner_id,
        is_system=is_system,
    )

    fields = []
    for i in range(num_fields):
        field = await TemplateFieldFactory.create_async(
            session,
            template_id=template.id,
            order=i,
        )
        fields.append(field)

    return template, fields
