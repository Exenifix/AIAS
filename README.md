# AIAS
AIAS (Artificial Intelligence AntiSpam) is an open-source Discord bot that has innovative moderation features, such as nextgen word filter and AI-based spam detection.

## AI Spam Detection
The bot is able to detect spam messages and even sequences of messages that are spam at pretty high accuracy. <!-- if well trained -->
### Quick Setup
1. Enable the system with `/antispam enable`
2. Set the ignored channels and roles with `/antispam ignore` command group

## NextGen Word Filter
AIAS also has an innovative word filter that can find blacklisted words in the most tough places, is able to filter out bypass symbols, apply antialias and even **search curse words between messages!**
### Quick Setup
1. Enable the system with `/blacklist enable`
2. Load the default words list with `blacklist template`
3. Add/remove words with `/blacklist add` and `/blacklist remove`
4. Set the ignored channels and roles with `/blacklist ignore` command group

### Blacklist Modes
- `common` blacklist mode searches for *exact matches* in words of the message.
- `wild` blacklist mode searches for *any occurences __inside__* of the words (including the exact match).
- `super` blacklist mode works just like `wild`, but ignores the spaces and is able to detect curse words across several messages. <br>
**All blacklist modes apply symbol filtering and lowercasing**. This means the bot automatically ignores all dots, commas, etc; it replaces the symbols that might mean letters as well.
Example: `I liKe ch33Se a l0T` -> `i like cheese a lot`. You can look at message preprocessing [here](https://github.com/Exenifix/AIAS/blob/master/utils/filters/blacklist.py).

## Character Whitelisting
Tired of members using fonts to avoid the word filter? With AIAS you can **allow only certain symbols** and highly lower the chance of bypass!

### Quick Setup
1. Use `/whitelist template` or `/whitelist setcharacters` to set the allowed characters
2. Activate the system with `/whitelist enable` (not recommended to turn on before setting the whitelisted characters)
3. Set the ignored characters and roles with `/whitelist ignore` command group

## NickFilter
Want to block members from setting inappropriate names? **NickFilter** from AIAS will do that easily! Nicknames containing blacklisted expressions defined in `blacklist` will be replaced with randomly generated nicknames. The generated names look good as well!

### Quick Setup
1. Enable the system with `/nickfilter enable`
2. Set the ignored roles with `/nickfilter ignore` command group

## Rules
Want to have a well ordered list of rules and be able to access rules by their keys? Possible with AIAS!

### Commands
- `/addrule`
- `/removerule`
- `/listrules`
- `/listruleskeys`
- `/rule`

## Administrative
### Logging
You can setup logging with `/admin setlogchannel` and remove it with `/admin disablelog`

### Managers
The managers are able to modify filters, however, they are not able to bypass them unless ignored.
You can modify managers list with the following commands:
- `/admin addmanagerrole`
- `/admin addmanagermember`
- `/admin removemanagerrole`
- `/admin removemanagermember`
