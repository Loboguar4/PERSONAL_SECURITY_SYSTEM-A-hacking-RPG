import random
import string
import time
import os

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def gerar_placa():
    letras = ''.join(random.choices(string.ascii_uppercase, k=3))
    numeros = ''.join(random.choices(string.digits, k=4))
    return f"{letras}-{numeros}"

def jogo_memoria():
    tempo = 3.0
    rodada = 1
    pontos = 0

    while True:
        placa = gerar_placa()
        clear()
        print(f"Rodada {rodada}")
        print("\nMemorize a placa:\n")
        print(f"   {placa}")
        time.sleep(tempo)

        clear()
        resposta = input("Digite a placa: ").strip().upper()

        if resposta != placa:
            print("\nFalha.")
            print(f"Placa correta: {placa}")
            print(f"Pontuação final: {pontos}")
            break

        pontos += 10
        rodada += 1
        tempo = max(0.8, tempo - 0.222)

        print("\nCorreto.")
        time.sleep(1)

if __name__ == "__main__":
    jogo_memoria()
