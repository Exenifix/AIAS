import inspect
import sys

from disnake import Forbidden, Interaction
from disnake.ext import commands

UNKNOWN = object()


class CustomError(commands.CommandError):
    pass


class DatabaseException(CustomError):
    def __init__(self, m="An exception occurred at the database."):
        super().__init__(m)


class NotIgnored(DatabaseException):
    def __init__(self, id: int):
        super().__init__(f"The object with ID of `{id}` is not ignored.")
        self.id = id


class WordNotFound(DatabaseException):
    def __init__(self, word: str, mode: str):
        super().__init__(
            f"The expression `{word}` is not added to `{mode}` blacklist and cannot be removed."
        )
        self.word = word
        self.mode = mode


class WordAlreadyExists(DatabaseException):
    def __init__(self, word: str, mode: str):
        super().__init__(
            f"The expression `{word}` is already added to `{mode}` blacklist!"
        )


class AlreadyIgnored(DatabaseException):
    def __init__(self, id: int):
        super().__init__(f"An object with ID {id} is already ignored.")


class AlreadyManager(DatabaseException):
    def __init__(self, id: int):
        super().__init__(f"An object with ID {id} is already a manager.")


class NotManager(DatabaseException):
    def __init__(self, id: int):
        super().__init__(f"An object with ID {id} is not a manager.")


class ManagerOnly(CustomError):
    def __init__(self):
        super().__init__(
            "Sorry, this command is **manager-only**. Ask an administrator of this server to grant you the privileges."
        )


class WordsThresholdExceeded(DatabaseException):
    def __init__(self):
        super().__init__(
            "Sorry, but there can be only **50** words per mode. Please delete some to add new."
        )


class RuleAlreadyExists(DatabaseException):
    def __init__(self, rule_key: str):
        super().__init__(f"A rule with key {rule_key} already exists.")


class RuleNotFound(DatabaseException):
    def __init__(self, rule_key: str):
        super().__init__(f"A rule with key {rule_key} doesn't exist.")


known_exceptions = [
    i[1] for i in inspect.getmembers(sys.modules[__name__], inspect.isclass)
]

known_exceptions.extend(
    [
        commands.MissingRequiredArgument,
        commands.ArgumentParsingError,
        commands.BadArgument,
        commands.CheckFailure,
        commands.CommandNotFound,
        commands.DisabledCommand,
        commands.CommandOnCooldown,
        commands.NotOwner,
        commands.MemberNotFound,
        commands.UserNotFound,
        commands.ChannelNotFound,
        commands.RoleNotFound,
        commands.MissingPermissions,
        commands.BotMissingPermissions,
        commands.MissingRole,
        commands.MissingAnyRole,
        Forbidden,
    ]
)
default_answers = {
    commands.CommandOnCooldown: "The command is on cooldown! Try again in {retry_after} seconds.",
    commands.MemberNotFound: 'Member "{error.argument}"" does not exist.',
    commands.UserNotFound: 'User "{error.argument}"" does not exist.',
    commands.ChannelNotFound: 'Channel "{error.argument}"" does not exist.',
    commands.RoleNotFound: 'Role "{error.argument}" does not exist.',
    commands.MissingPermissions: "You need the following permission(s) to use this command:\n\
`{missing_perms}`",
    commands.BotMissingPermissions: "Bot needs the following permission(s) to perform this command:\n\
`{missing_perms}`",
    commands.MissingRole: "You need `{error.missing_role}` role to use this command",
    commands.MissingAnyRole: "You need any of the following roles to use this command:\n\
`{missing_roles}`",
    Forbidden: "Bot does not have permission to do this. It is probably missing one of required permissions, check that the bot has all required permissions in this channel",
}


def get_error_message(
    ctx: commands.Context | Interaction, error: commands.CommandError
):
    if type(error) not in known_exceptions:
        return UNKNOWN

    elif type(error) in default_answers:
        response: str = default_answers[type(error)]
        retry_after = int(getattr(error, "retry_after", 0))
        try:
            missing_perms = ", ".join([str(perm) for perm in error.missing_permissions])
        except AttributeError:
            missing_perms = None
        try:
            missing_roles = ", ".join([str(role) for role in error.missing_roles])
        except AttributeError:
            missing_roles = None

        return response.format(
            ctx=ctx,
            error=error,
            retry_after=retry_after,
            missing_perms=missing_perms,
            missing_roles=missing_roles,
        )

    else:
        return str(error)
