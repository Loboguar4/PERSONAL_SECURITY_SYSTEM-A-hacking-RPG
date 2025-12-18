# PERSONAL_SECURITY_SYSTEM - ver. 0.9.0-beta ~~ Desenvolvido pelo Bandeirinha
                                                                                                    
                                                                                                    
                                                                                                    
                                                                                                    
           .                    .~J~                                                                
           ..                :!YPPPG7                                                               
            ..               ?GPPPPPGJ                                                              
             :.               !PPPPPPPY.                                                            
             .:.               :PPPPPPPP:                                                           
              ::.               .YP55P5PP^                                                          
              .~:                .J5YYYYYP!                                                         
               :!.                 !YYYYYY57                                                        
               .!^.                 ^YYYYJJY?.                                                      
              ..^?:..                :JJJJJJJ?.                                                     
              ..:?!:..                .7???????:                                                    
              ..:!Y~:.                  !?777!!7^                                                   
              ..:^5?^:.                  ^!!!7777~                                                  
              ..^^JP7^:.      .           :777!!!7~                                                 
             ...^~7BY!^.... ...            .!7!!!!!!.                                               
             ...:!7GBJ!:.......              ~!!!!!!7:                                              
            ...::~75&P?~^:..::.........       ~7!!7!!!:                                             
          .....:^~7J&#57~^::^:.........        ^7!!!!!7^                                            
          ....::^!7J#&BY7~~~~::....:....        .!777!!!~                                           
         ...::^^~!?JB@#PY777~^::::::......       .!!!!!!!!.        :^::.                            
        ....::^~!7?YG@&BPJJ?~^^^~^:::..........   .~!!!!!!!.      B&&#BGJ.                          
       .....:^^!77?YB@@&BP5?!!!!~^^:::::::..........^!!!!!77:     ~B&&&##B~                         
      .....::^~!?JY5B@@&##GJ???!~~^^^^^^:::..^5PP55J?J!!7!~.7JP^    ^7Y55J.                         
      ...:::^^~7?Y5P#@@@&&G55YJ7!!!!~~~^::...5@@BGG#&#P^: ~^^??7:. ..                               
     ...:::^~!7??YPB#@@@@&#BP5JJJ?7!!~^^:::..^B@@@@@@#:  :!Y?!~~...     ~GB57:                      
     ...::^^~!?YY5GB&@@@@&&BGP5YJ?7!!~^^^::::..^!7?!^.  ^!!~?J~:::::    &@&&&#G^                    
    ....:^^~~!7J5PB#&@@@@@&#BG5YJ??7!~~~~^^::::..... .^!?!!~~^J7^^:.    ^&@@&&&#.                   
    ....::^~~!7JYPB#&@@@@@&#BG5YJ??7!!~~~^^::::.::.:!!~^::. .^^~~^:      .7G##BY:                   
    ....:::^~!7?YPG#&@@@@@&#GP5YJ??7!~^^^^:::......:?7~^!^. .^ .~:.:^.                              
     ....:^^~!!?Y5GB&@@@@&#BGPYJ?77!~^^^^:::.....   :!5GJ.     :^~777!.                             
      ....::^!!7?J5G#@@@@#BG5JJ??7!~^^^:::......      .~^.     ^7!!!!!!.                            
      ....::^^~!7JY5B@@&&#P5Y?77!!~~~^^::......                 ^!!!!!!!:                           
      .....:::^~!?JJG@@&#BY???!~^^^^^^:::.....                   :!!!!!!7^                          
       ......:^~!!7?G@&#G5Y!~~~~^:::::........                    .!!!!!!!~                         
        .....::^~~!?G@&G5??!^^^^^::...........                      ~!~~!!7!.                       
         .....::^^!?B@#5?!!~::::::......                             ^!!!!!!!.                      
         . .....:^!?#&G?!^^^:.........                                ^!!!!!!!:                     
            .....:~J&BJ!^::::........                                  .!!!!!!!^                    
              ...:~5#57^:......                                         .!!!!!!!~                   
               ..:!GP?~:.......                                           ~7!~!!7!.                 
                .:7BJ~:...   .                                             ^!!!!!!!.                
                .:J5!^..                                                    :!!!!!!!:               
               ..:57^:.                                                      .!!!!!!!^              
               ..!J^:..                                                       .~!!!!!!^             
               ..J!:..                                                          ~7!~~!!~.           
               .^7:..                                                            :!!!!!!!.          
               .7^.                                                               :!!!!!!!:         
               ^~.                                                                 .!!!!!!!^        
              .~:                                                                    ~!!!!!!.       
              ^:.                                                                     ^!~:.         
             .:.                                                                                    
            .:                                                                                      
            .                                                                                       
           .                                                                                        
                                                                                                    

             
    Para apoiar este e mais projetos: pixgg.com/bandeirinha

    
**PERSONAL_SECURITY_SYSTEM** é um jogo single-player em modo texto (terminal) que simula um ecossistema dinâmico de IAs, reputações faccionais, operações de invasão abstratas, eventos mundiais e missões narrativas. O projeto é **ficcional** e não ensina técnicas reais de intrusão ou instruções práticas de ataque.

<img src="https://img.shields.io/badge/status-active-brightgreen">  
<img src="https://img.shields.io/badge/engine-python3-blue">

> **Aviso de origem:** Este projeto é inspirado conceitualmente em *Endgame: Singularity*, mas **não utiliza conteúdo oficial** do jogo original e **não é afiliado** aos autores originais. Todo o lore, personagens, nomes e textos deste repositório são originais ou reescritos para evitar uso de material protegido.

---

## Estado do projeto

- **Status:** Em desenvolvimento / não-final — versão experimental.  
- Pode conter bugs, código incompleto e mudanças de API entre commits.  
- Sem save/load game.__
- Código aberto e **redistribuível: licenciado sob **GNU General Public License v3.0 ou posterior** (SPDX: `GPL-3.0-or-later`). Veja a seção *Licença* abaixo.

NOTA:
Decidi deixar o jogo em copyleft primeiro porque tudo começou como uma oportunidade para interagir com técnicas relativamente mais complexas dentro da linguagem Python. É um projeto para fins educacionais e de entretenimento. Segundo porque provavelmente não terei tempo até deixar o jogo como eu gostaria, pois a minha saúde física e mental estão atualmente péssimas, junto ao meu financeiro. Mas já fico imensamente satisfeito de ter conseguido publicar uma versão beta pelo menos... Então contarei com a comunidade Open Source para corrigir, melhorar, expandir e espalhar este "worm".

---

## Recursos principais

- Mundo procedural com regiões, tendências e desbloqueios.  
- IAs inimigas com perfis (Pirata, Federal, Hacktivista, Genérico).  
- Reputação por facção, missões narrativas e eventos que afetam gameplay.  
- Alvos gerados diariamente com chance de honeypot.  
- Sistema de risco, trace, multas e possibilidade de prisão (mecânicas de jogo).  
- Skills (recon, exploit, stealth), inventário e assets com renda passiva.  
- Tudo rodando via terminal — sem GUI.

---

## Requisitos

- **Python 3.8 ou superior** (testado com 3.8–3.11).  
- Sistema operacional: Linux, macOS ou Windows (com `python3` / `py`).  
- **Sem dependências externas**: apenas biblioteca padrão do Python.  
- Recomendado: terminal que suporte UTF-8 para melhor renderização dos caracteres usados nas animações ASCII.

Verifique a versão do Python:

```bash
python3 --version
# ou no Windows
py --version



    Instalação (passo a passo)

1. Clone o repositório:

git clone https://github.com/Loboguar4/PERSONAL_SECURITY_SYSTEM.git
cd PERSONAL_SECURITY_SYSTEM


2. (Opcional) Crie e ative um ambiente virtual:

python3 -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows (PowerShell: .venv\Scripts\Activate.ps1)


3. Execute o jogo:

python3 PERSONAL_SECURITY_SYSTEM.py
# ou no Windows
py PERSONAL_SECURITY_SYSTEM.py

