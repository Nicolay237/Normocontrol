_registered = False


def register_actions() -> None:
    global _registered
    if _registered:
        return
    import app.access.actions  # noqa: F401
    import app.chats.actions  # noqa: F401
    import app.chats.syncs  # noqa: F401
    import app.folders.actions  # noqa: F401
    import app.folders.syncs  # noqa: F401
    import app.groups.actions  # noqa: F401
    import app.labs.actions  # noqa: F401
    import app.normocontrol.actions  # noqa: F401
    import app.normocontrol.syncs  # noqa: F401
    import app.pages.actions  # noqa: F401
    import app.pages.syncs  # noqa: F401
    import app.provenance.actions  # noqa: F401
    import app.provenance.syncs  # noqa: F401
    import app.sharing.actions  # noqa: F401
    import app.source_control.actions  # noqa: F401
    import app.tests.actions  # noqa: F401
    import app.tests.attempt_actions  # noqa: F401
    import app.tests.syncs  # noqa: F401
    import app.tests.teacher_actions  # noqa: F401
    import app.users.actions  # noqa: F401
    import app.workspace.actions  # noqa: F401
    import app.workspace.syncs  # noqa: F401
    import app.ws.system  # noqa: F401

    _registered = True
