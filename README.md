# AIAS

AIAS (Artificial Intelligence AntiSpam) is an open-source Discord bot that has innovative moderation features, such as
nextgen word filter and AI-based spam detection.

## Cool Banner

![Discord Bots](https://top.gg/api/widget/962093056910323743.svg)<br>

## Links

- **[Support Server](https://discord.gg/TsSAfdN4hS)**
- **[Invite Bot](https://discord.com/api/oauth2/authorize?client_id=962093056910323743&permissions=1374524140630&scope=bot%20applications.commands)**

## AI Spam Detection

The bot is able to detect spam messages and even sequences of messages that are spam at pretty high
accuracy. <!-- if well trained -->

### Quick Setup

1. Enable the system with `/antispam enable`
2. Set the ignored channels and roles with `/antispam ignore` command group

## NextGen Word Filter

AIAS also has an innovative word filter that can find blacklisted words in the most tough places, is able to filter out
bypass symbols, apply antialias and even **search curse words between messages!**

### Quick Setup

1. Enable the system with `/blacklist enable`
2. Load the default words list with `blacklist template` OR skip this step if you want to set up entirely custom bad words list
3. Add/remove words with `/blacklist add` and `/blacklist remove`
4. Set the ignored channels and roles with `/blacklist ignore` command group

## Antiraid

Antiraid makes sure huge amount of members doesn't join just at once. **This feature is in BETA!**

### Quick Setup

1. Enable the system with `/antiraid enable`
2. Setup rate per using `/antiraid setup`
3. Pick the punishment with `/antiraid setpunishment`

### Blacklist Modes

- `common` blacklist mode searches for *exact matches* in words of the message.
- `wild` blacklist mode searches for *any occurences __inside__* the words (including the exact match).
- `super` blacklist mode works just like `wild`, but ignores the spaces and is able to detect curse words across several
  messages. <br>
  **All blacklist modes apply symbol filtering and lowercasing**. This means the bot automatically ignores all dots,
  commas, etc.; it replaces the symbols that might mean letters as well.
  Example: `I liKe ch33S.,e a l0T` -> `i like cheese a lot`. You can look at message
  preprocessing [here](https://github.com/Exenifix/AIAS/blob/master/utils/filters/blacklist.py).

## Character Whitelisting

Tired of members using fonts to avoid the word filter? With AIAS, you can **allow only certain symbols** and highly lower
the chance of bypass!

### Quick Setup

1. Use `/whitelist template` or `/whitelist setcharacters` to set the allowed characters
2. Activate the system with `/whitelist enable` (not recommended to turn on before setting the whitelisted characters)
3. Set the ignored characters and roles with `/whitelist ignore` command group

## Autoslowmode
Autoslowmode helps to control the message flow in your channels by editing channel's slowmode based on amount of messages sent per certain interval! **Maximum 10 channels per server**

### Commands
There are only 2 commands: `/autoslowmode addchannel` to add a channel and `/autoslowmode removechannel`.

## NickFilter

Want to block members from setting inappropriate names? **NickFilter** from AIAS will do that easily! Nicknames
containing blacklisted expressions defined in `blacklist` will be replaced with randomly generated nicknames. The
generated names look good as well!

### Quick Setup

1. Enable the system with `/nickfilter enable`
2. Set the ignored roles with `/nickfilter ignore` command group

## Rules

Want to have a well-ordered list of rules and be able to access rules by their keys? Possible with AIAS!

### Commands

- `/addrule`
- `/removerule`
- `/listrules`
- `/listruleskeys`
- `/rule`

## Administrative

### Logging

You can set up logging with `/admin setlogchannel` and remove it with `/admin disablelog`

### Managers

The managers are able to modify filters, however, they are not able to bypass them unless ignored.
You can modify managers list with the following commands:

- `/admin addmanagerrole`
- `/admin addmanagermember`
- `/admin removemanagerrole`
- `/admin removemanagermember`
