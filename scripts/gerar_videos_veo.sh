#!/bin/bash
# Gera 2 videos curtos (5s cada) via Veo 3 para headers de templates WABA
# Output: /Users/tiagolau/Devs/MasterClinic/media/

set -e
source ~/.claude/.env

OUTDIR="/Users/tiagolau/Devs/MasterClinic/media"
LOGDIR="/Users/tiagolau/Devs/MasterClinic/logs"
mkdir -p "$OUTDIR" "$LOGDIR"

# Modelo Veo 3 fast (mais barato, suficiente para header de template)
MODEL="veo-3.0-fast-generate-001"

# Video 1: recepcao de clinica (para masterclinic_utilidade_01)
PROMPT_1="A clean modern medical clinic reception desk, a friendly receptionist in white uniform looking at a patient chart on a computer screen, soft natural lighting, professional medical environment, no text overlay, no logos, 5 seconds, cinematic"

# Video 2: medico em consultorio (para masterclinic_paciente_em_tratamento)
PROMPT_2="A professional doctor in white coat sitting at a desk in a bright modern medical office, looking thoughtfully at a patient file, warm and reassuring atmosphere, no text overlay, no logos, no face close-up, 5 seconds, cinematic"

submit_job() {
  local prompt="$1"
  local label="$2"

  echo "[$(date +%H:%M:%S)] Submetendo job: $label"
  RESPONSE=$(curl -s -X POST \
    "https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:predictLongRunning?key=${GOOGLE_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
      \"instances\": [{ \"prompt\": \"${prompt}\" }],
      \"parameters\": {
        \"aspectRatio\": \"16:9\",
        \"durationSeconds\": 5,
        \"resolution\": \"720p\",
        \"personGeneration\": \"allow_adult\"
      }
    }")
  echo "$RESPONSE" > "$LOGDIR/veo_${label}_submit.json"
  OP_NAME=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name',''))")
  echo "$OP_NAME" > "$LOGDIR/veo_${label}_opname.txt"
  echo "  -> operation: $OP_NAME"
}

submit_job "$PROMPT_1" "recepcao"
submit_job "$PROMPT_2" "dr_wilton"

echo ""
echo "Jobs submetidos. Polling a cada 30s ate 10min."

poll_job() {
  local label="$1"
  local op_name
  op_name=$(cat "$LOGDIR/veo_${label}_opname.txt")
  if [ -z "$op_name" ]; then
    echo "[$label] sem op_name, pulando"
    return 1
  fi

  for i in {1..20}; do
    sleep 30
    STATUS=$(curl -s "https://generativelanguage.googleapis.com/v1beta/${op_name}?key=${GOOGLE_API_KEY}")
    DONE=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('done',False))" 2>/dev/null || echo "False")
    echo "[$(date +%H:%M:%S)] [$label] done=$DONE (tentativa $i/20)"
    if [ "$DONE" = "True" ]; then
      echo "$STATUS" > "$LOGDIR/veo_${label}_result.json"
      VIDEO_URI=$(echo "$STATUS" | python3 -c "
import sys,json
d = json.load(sys.stdin)
try:
    print(d['response']['generateVideoResponse']['generatedSamples'][0]['video']['uri'])
except (KeyError, IndexError):
    try:
        print(d['response']['videos'][0]['uri'])
    except (KeyError, IndexError):
        print('')
")
      echo "  -> video URI: $VIDEO_URI"
      if [ -n "$VIDEO_URI" ]; then
        curl -s -o "$OUTDIR/${label}.mp4" "${VIDEO_URI}&key=${GOOGLE_API_KEY}"
        echo "  -> salvo em $OUTDIR/${label}.mp4 ($(stat -f%z "$OUTDIR/${label}.mp4") bytes)"
        return 0
      fi
      return 1
    fi
  done
  echo "[$label] timeout"
  return 1
}

poll_job "recepcao" &
PID1=$!
poll_job "dr_wilton" &
PID2=$!
wait $PID1 $PID2

echo ""
echo "[$(date +%H:%M:%S)] Concluido. Arquivos:"
ls -la "$OUTDIR"
