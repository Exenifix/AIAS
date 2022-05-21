import disnake

rules_cache: dict[int, list[str]] = {}


def invalidate_rules(id: int):
    rules_cache.pop(id, None)


async def autocomplete_rules(inter: disnake.ApplicationCommandInteraction, arg: str):
    arg = arg.lower()
    if inter.guild.id in rules_cache:
        result = rules_cache[inter.guild.id]
    else:
        rules = list(
            (await inter.bot.db.get_guild(inter.guild.id).get_all_rules()).keys()
        )
        rules_cache[inter.guild.id] = rules
        result = rules

    results = [r for r in result if arg in r.lower()]
    if len(results) > 10:
        results = results[:10]

    return results
