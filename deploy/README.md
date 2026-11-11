# Tremor en vivo en una máquina propia

GitHub corre las franjas de radio; una máquina propia escucha **en continuo** y manda el aviso al chat en el mismo
minuto. Oracle Cloud regala una (always free: 4 núcleos ARM, 24 GB) que alcanza para la zona de un cliente.

## Una vez, a mano (10 minutos)

1. Cuenta en https://www.oracle.com/cloud/free/ (pide tarjeta para verificar; el plan free no cobra).
2. **Create a VM instance**: imagen *Ubuntu 22.04* (aarch64), shape *VM.Standard.A1.Flex* con 4 OCPU y 24 GB,
   y descarga la clave SSH que genera.
3. Con la IP pública de la máquina:

```bash
ssh -i clave.key ubuntu@IP
curl -fsSL https://raw.githubusercontent.com/nicosil02/tremor/main/deploy/instalar.sh | bash -s -- Bateas
nano ~/tremor/.env        # LLM_API_KEY, GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
sudo systemctl restart tremor-vivo
journalctl -u tremor-vivo -f   # el log en vivo
```

Desde ahí corre sola, se reinicia si se cae y arranca con la máquina. Para otra empresa: el mismo comando con su
nombre. Para actualizar el código: `cd ~/tremor && git pull && sudo systemctl restart tremor-vivo`.
