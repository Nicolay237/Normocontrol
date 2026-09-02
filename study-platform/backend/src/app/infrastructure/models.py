"""Import every model once so Alembic can discover complete metadata."""

from app.access.models import ResourceAcl, ResourceAclRequiredGroup
from app.audit.models import AuditEvent
from app.blocks.models import PageBlock
from app.chats.models import Chat, ChatMessage, ResourceChat
from app.files.models import FileAttachment, StoredFile
from app.folders.models import Folder
from app.groups.models import Group, GroupMembership, GroupPolicy
from app.labs.models import (
    LabGitSubmissionSnapshot,
    LabSettings,
    LabSubmission,
)
from app.normocontrol.models import (
    NormocontrolCheck,
    NormocontrolRun,
    NormocontrolSettings,
)
from app.pages.models import Page, PageEvent, PageRevision
from app.provenance.models import (
    CitationSource,
    ContentProvenance,
    PageInputEvent,
    ProvenanceReport,
)
from app.sharing.models import RevisionShareLink
from app.source_control.models import (
    SourceControlConnection,
    SourceControlInstance,
    SourceControlOAuthState,
)
from app.tests.models import (
    AttemptAnswer,
    AttemptEvent,
    AttemptQuestion,
    Question,
    QuestionBank,
    QuestionVersion,
    Test,
    TestAttempt,
    TestQuestionSlot,
    TestVersion,
)
from app.users.models import (
    AuthIdentity,
    AuthSession,
    ExternalUserBinding,
    TakeoverChallenge,
    User,
    UserImportPreview,
)
from app.workspace.models import UserPin

__all__ = [
    "AuthIdentity",
    "AuthSession",
    "AuditEvent",
    "AttemptAnswer",
    "AttemptEvent",
    "AttemptQuestion",
    "Chat",
    "ChatMessage",
    "CitationSource",
    "ContentProvenance",
    "Folder",
    "FileAttachment",
    "ExternalUserBinding",
    "Group",
    "GroupMembership",
    "GroupPolicy",
    "LabGitSubmissionSnapshot",
    "LabSettings",
    "LabSubmission",
    "NormocontrolCheck",
    "NormocontrolRun",
    "NormocontrolSettings",
    "Page",
    "PageEvent",
    "PageInputEvent",
    "PageRevision",
    "PageBlock",
    "ResourceAcl",
    "ResourceAclRequiredGroup",
    "ResourceChat",
    "RevisionShareLink",
    "SourceControlConnection",
    "SourceControlInstance",
    "SourceControlOAuthState",
    "ProvenanceReport",
    "Question",
    "QuestionBank",
    "QuestionVersion",
    "StoredFile",
    "TakeoverChallenge",
    "Test",
    "TestAttempt",
    "TestQuestionSlot",
    "TestVersion",
    "User",
    "UserImportPreview",
    "UserPin",
]
