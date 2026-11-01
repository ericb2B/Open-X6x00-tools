#!/usr/bin/env bash
set -Eeuo pipefail

DIR="$HOME/tci-audio"
PYTHON="$DIR/venv/bin/python"

RADIO_IP="192.168.1.200"
RADIO_PORT="50001"

SINK="tci_rx"
SOURCE="tci_micro"

SINK_MODULE=""
SOURCE_MODULE=""

cleanup() {
    echo
    echo "Arrêt du flux TCI..."

    if [[ -n "$SOURCE_MODULE" ]]; then
        pactl unload-module "$SOURCE_MODULE" 2>/dev/null || true
    fi

    if [[ -n "$SINK_MODULE" ]]; then
        pactl unload-module "$SINK_MODULE" 2>/dev/null || true
    fi

    echo "Périphériques virtuels supprimés."
}

if [[ ! -x "$PYTHON" ]]; then
    echo "Python du venv introuvable : $PYTHON"
    exit 1
fi

"$PYTHON" -c "import numpy, sounddevice, websockets" || {
    echo "Modules Python manquants dans le venv."
    exit 1
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Création du périphérique audio virtuel..."

SINK_MODULE=$(pactl load-module module-null-sink \
    sink_name="$SINK" \
    rate=48000 \
    channels=2 \
    sink_properties=device.description=TCI_RX)

SOURCE_MODULE=$(pactl load-module module-remap-source \
    master="$SINK.monitor" \
    source_name="$SOURCE" \
    source_properties=device.description=TCI_Microphone)

echo
echo "======================================"
echo " X6100 TCI -> MICROPHONE VIRTUEL"
echo "======================================"
echo "Radio : $RADIO_IP:$RADIO_PORT"
echo "Micro : $SOURCE"
echo
echo "Démarrage du flux..."
echo "Arrêt : Ctrl+C"
echo

export PULSE_SINK="$SINK"

"$PYTHON" "$DIR/tci_rx.py"
