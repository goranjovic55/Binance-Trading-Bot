from typing import Dict, Tuple


def load_correct_creds(creds: Dict) -> Tuple[str, str]:
    """Returns the binance API key details from the config

    Args:
        creds (dict): the dict containing the details from the config

    Returns:
        tuple[str, str]: the binance access_key followed by the secret_key)
    """
    return creds["prod"]["access_key"], creds["prod"]["secret_key"]


def load_telegram_creds(creds: Dict) -> Tuple[str, str, str, str]:
    return (
        creds["telegram"]["TELEGRAM_BOT_TOKEN"],
        creds["telegram"]["TELEGRAM_BOT_ID"],
        creds["discord"]["TEST_DISCORD_WEBHOOK"],
        creds["discord"]["LIVE_DISCORD_WEBHOOK"],
    )


def test_api_key(client, BinanceAPIException) -> Tuple[bool, str]:
    """Checks to see if API keys supplied returns errors

    Args:
        client (class): binance client class
        BinanceAPIException (clas): binance exeptions class

    Returns:
        bool | msg: true/false depending on success, and message
    """
    try:
        client.get_account()
        return True, "API key validated succesfully"

    except BinanceAPIException as e:

        if e.code in [-2015, -2014]:
            bad_key = "Your API key is not formatted correctly..."
            america = "If you are in america, you will have to update the config to set AMERICAN_USER: True"
            ip_b = "If you set an IP block on your keys make sure this IP address is allowed. check ipinfo.io/ip"

            msg = f"Your API key is either incorrect, IP blocked, or incorrect tld/permissons...\n  most likely: {bad_key}\n  {america}\n  {ip_b}"

        elif e.code in [-2021, -1021]:
            issue = "https://github.com/CyberPunkMetalHead/Binance-volatility-trading-bot/issues/28"
            desc = "Ensure your OS is time synced with a timeserver. See issue."
            msg = f"Timestamp for this request was 1000ms ahead of the server's time.\n  {issue}\n  {desc}"

        else:
            msg = "Encountered an API Error code that was not caught nicely, please open issue...\n"

        return False, msg

    except Exception as e:
        return False, f"Fallback exception occured:\n{e}"
