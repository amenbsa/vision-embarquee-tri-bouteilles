# Système de Vision Embarquée — Contrôle Qualité Bouteilles
**Mini Projet IIA4 — INSAT Tunis 2025/2026**

## Description
Système de tri automatique de bouteilles par vision embarquée sur Raspberry Pi 5.

**Critères de classification :**
- Couleur du bouchon (bleu / rouge / absent) → filtrage HSV
- Taux de remplissage → gradient de Sobel

## Matériel
- Raspberry Pi 5 (4 Go RAM)
- Caméra CSI Module V2 (Sony IMX219, 8MP)
- Capteur IR (GPIO 17)
- Servomoteur SG90 (GPIO 18, PWM 50Hz)

## Lancer la simulation QEMU
```bash
python3 bottle_rpi5.py
```

## Résultats
- Précision couleur : > 95%
- Résolution spatiale : 0.567 mm/px à 30 cm
- Fréquence : ~20 fps (mode headless)

## Équipe
Abrougui Zied · Amiri Fatma · Atoui Fares · Azouzi Wejden
Ben Sik Ali Amen · Fandouli Elyes · Mrad Rayen · Zidane Mohamed
