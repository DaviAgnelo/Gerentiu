"""Least-privilege permission rules shared by Gerentiu features."""

from collections.abc import Iterable


PermissionRequirement = tuple[str, str]

ANTISPAM_PUNISHMENT_ORDER = ("warn", "delete", "timeout", "kick", "ban")


def required_antispam_permissions(max_punishment: str) -> tuple[PermissionRequirement, ...]:
    """Return Discord permission attributes needed by the punishment progression."""
    if max_punishment not in ANTISPAM_PUNISHMENT_ORDER:
        max_punishment = "timeout"

    max_index = ANTISPAM_PUNISHMENT_ORDER.index(max_punishment)
    requirements: list[PermissionRequirement] = [
        ("manage_messages", "Manage Messages"),
    ]

    if max_index >= ANTISPAM_PUNISHMENT_ORDER.index("timeout"):
        requirements.append(("moderate_members", "Moderate Members"))
    if max_index >= ANTISPAM_PUNISHMENT_ORDER.index("kick"):
        requirements.append(("kick_members", "Kick Members"))
    if max_index >= ANTISPAM_PUNISHMENT_ORDER.index("ban"):
        requirements.append(("ban_members", "Ban Members"))

    return tuple(requirements)


def required_antiraid_permissions(action: str) -> tuple[PermissionRequirement, ...]:
    """Return the extra permissions needed by the configured anti-raid action."""
    if action == "alert":
        return ()

    return (("manage_channels", "Manage Channels"),)


def missing_permission_labels(
    permissions: object,
    requirements: Iterable[PermissionRequirement],
) -> list[str]:
    return [
        label
        for attribute, label in requirements
        if not bool(getattr(permissions, attribute, False))
    ]


def missing_antispam_permissions(permissions: object, max_punishment: str) -> list[str]:
    return missing_permission_labels(
        permissions,
        required_antispam_permissions(max_punishment),
    )


def missing_antiraid_permissions(permissions: object, action: str) -> list[str]:
    return missing_permission_labels(
        permissions,
        required_antiraid_permissions(action),
    )
