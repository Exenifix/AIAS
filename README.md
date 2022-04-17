# AIAS
AIAS (Artificial Intelligence AntiSpam) is an open-source Discord bot that has innovative moderation features, such as nextgen word filter and AI-based spam detection.

## Features
- AI based antispam detection
- innovative word filter with 3 modes
- character whitelisting
- nicknames filter + random nickname generation
- rules system
- simple moderation system
- ability to block messages by reacting to them or using user command

## FAQ
1. **How do I add/remove a word to/from blacklist?**
> Use `/blacklist add` or `/blacklist remove` correspondingly.
2. **What do different blacklist modes do?**
> - `common` blacklist mode searches for *exact matches* in words of the message.
> - `wild` blacklist mode searches for *any occurences __inside__* of the words (including the exact match).
> - `super` blacklist mode works just like `wild`, but ignores the spaces and is able to detect curse words across several messages. <br>
> **All blacklist modes apply symbol filtering and lowercasing**. This means the bot automatically ignores all dots, commas, etc; it replaces the symbols that might mean symbols as well.
> Example: `I liKe ch33Se a l0T` -> `i like cheese a lot`. You can look at message preprocessing [here](https://github.com/Exenifix/AIAS/blob/master/utils/filters/blacklist.py)
3. **The message was marked as spam but it is not, what do I do?**
> The AI model is constantly being improved and will never be ideal. When a message is marked as spam, it is shown up in logs with the button "Not a Spam" below (if you have log channel set up). You can press the button to report the message to us.
> **You can also use `/train` to help us improve the model!**
4. **How do I add a manager?**
> Use `/admin addrole` or `/admin addmember`.
5. **How do I disable a filter in some channels or for some roles?**
> All the filters have subcommand group `ignore` which has required subcommands for disabling a filter in some channels or for some roles.
