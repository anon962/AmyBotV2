send() {
    echo "$2: $1"
    screen -S "$2" -X stuff "$1^M"
}

screen -dmS "bot_amy"
send "../venv/bin/python ./run_bot.py" "bot_amy"

screen -dmS "server_amy"
send "../venv/bin/python ./run_server.py" "server_amy"

