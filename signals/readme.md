# SIGNALS folder

This folder is used as message bus between external signal modules and main bot and should contain files with `.exs` extension.
These files should contain list of pairs to be traded by the bot.

Ex `module1.exs`:
ETHUSDT  
BTCUSDT

Custom modules can create this kind of files here and the bot will take care to buy the pairs and remove the file.