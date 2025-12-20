#!/usr/bin/env python3
"""
# PERSONAL_SECURITY_SYSTEM - ver. 0.9.1-beta
# Copyright (C) 2025 Bandeirinha
# Licensed under the GNU GPL v3.0 or later

NOTAS DE ATUALIZAÇÃO:

- Imposição de limites para jobs e study, exigindo mínimo de foco necessário.

- Um clear_screen() implementado ao iniciar o jogo

"""

import time
import random
import sys
import uuid
import hashlib
import os
from collections import deque
from datetime import datetime, timedelta

# Configurações globais
GAME_OVER_ON_JAIL = True
START_DATE = datetime(2095, 11, 1, 8, 0)
RNG_SEED = None  # coloque um int para runs reproduzíveis
MIN_FOCUS_STUDY = 35
MIN_FOCUS_JOB = 25

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

#def clear_screen():
#    print("\033c", end="")

if RNG_SEED is not None:
    random.seed(RNG_SEED)


# -------------------- Modelos --------------------
class Player:
    def __init__(self):
        self.name = ""
        self.money = 75.0
        self.focus = 100.0
        self.ritaline_pills = 0
        self.ritaline_addiction = 0.0  # 0 a 100, chance de vício
        self.time = START_DATE
        self.skills = {"recon": 1.0, "exploit": 1.0, "stealth": 1.0}
        self.risk = 0.0  # risco individual (mantido fora dos metadados regionais)
        self.fs = default_filesystem()
        self.cwd = "/home"
        self.inventory = []
        self.inventory_limit = 6
        self.assets = []
        self.jailed_until = None
        self.knowledge = 0
        self.game_over = False
        # reputações globais do jogador
        self.reputation = {"hacktivists": 0, "state": 0, "crime": 0}
        self.command_history = deque(maxlen=200)
        self.known_enemy_fps = {}   # {fingerprint: {"id":ai.uid, "first_seen": datetime, "meta":{}}}
        self.local_alerts = deque(maxlen=200)  # mensagens importantes recebidas
        self.region = "Local"  # região onde o jogador está baseado/inicialmente
        self.next_job_state_time = None

    def record_enemy_fingerprint(self, ai):
        fp = ai.fingerprint
        if not fp or fp == "UNKNOWN":
            return
        if fp not in self.known_enemy_fps:
            self.known_enemy_fps[fp] = {
                "id": ai.uid,
                "first_seen": self.time,
                "level": ai.level,
                "note": "",
                "type_known": getattr(ai, "type", "Unknown") if getattr(ai, "revealed_type", False) else None,
            }

    def push_alert(self, text, delay=True):
        ts = self.time.strftime("%Y-%m-%d %H:%M")
        self.local_alerts.append(f"{ts} | {text}")
        print(f"\n...{text}\n")
        if delay:
            time.sleep(1.0)

    def hours_pass(self, hrs, world):
        """Avança tempo e dispara efeitos diários quando um dia completo passa."""

        # Redução de foco
        decay = hrs * 0.32231
        addicted = getattr(self, "ritaline_addicted", False)

        # Caso ainda esteja viciado, foco decai mais rápido
        if addicted:
            decay *= 2

        self.focus = max(0.0, self.focus - decay)

        old_time = self.time
        self.time += timedelta(hours=hrs)

        # risco decai com o tempo
        self.risk = max(0.0, self.risk - hrs * 0.17)

        # Decaimento do vício
        self.ritaline_addiction = max(0.0, self.ritaline_addiction - hrs * 0.12)

        # Se vício chegou a zero → cura da dependência
        if addicted and self.ritaline_addiction <= 0:
            self.ritaline_addicted = False
            self.push_alert("Seu vício foi superado. Seu foco agora decai normalmente.")

        # renda passiva e efeitos de dia
        self._generate_passive_income(old_time, self.time)
        days_passed = (self.time.date() - old_time.date()).days
        for _ in range(days_passed):
            world.advance_day(self)

    def in_jail(self):
        return self.jailed_until and self.time < self.jailed_until

    def _generate_passive_income(self, t0, t1):
        days = (t1.date() - t0.date()).days
        if days <= 0:
            return
        income = 0.0
        for a in self.assets:
            income += a.get("income_per_day", 0.0) * days
        if income > 0:
            self.money += income
            # manutenção eventual
            if random.random() < 0.05 * days:
                cost = min(self.money, 30 * days)
                self.money -= cost

    def record_command(self, line):
        self.command_history.append(f"{self.time.strftime('%Y-%m-%d %H:%M')} $ {line}")

    def maybe_game_over(self):
        if self.in_jail() and GAME_OVER_ON_JAIL:
            self.game_over = True


class Target:
    def __init__(self, tid, name, security, reward, trace_speed, region=None, hints=None, honeypot=False):
        self.id = tid
        self.name = name
        self.security = security
        self.reward = reward
        self.trace_speed = trace_speed
        self.region = region
        self.hints = hints or []
        self.honeypot = honeypot
        self.fake_security = security


# -------------------- Mundo dinâmico --------------------
class World:
    def __init__(self):
        self.day = 0
        self.regions = self._init_regions()
        self.global_targets = []       # pool de alvos disponíveis (objetos Target)
        self.next_tid = 1
        self.enemy_ais = []            # lista de EnemyAI ativos
        self.last_scan = []
        self.last_alerts = deque(maxlen=500)
        self.ai_activity_logs = []     # feedback textual das IAs (novo, antes logs indefinido)
        self.generate_daily_targets()
        # Definição completa das missões especiais
        self.missions_def = {
            # ===========================
            # HACKTIVISTS — ROTAS DA VERDADE
            # ===========================
            "hx_m1": {
                "min_rep": {"hacktivists": 6},
                "unlock_next": "hx_m2",
            },
            "hx_m2": {
                "min_rep": {"hacktivists": 10},
                "unlock_next": "hx_m3",
            },
            "hx_m3": {
                "min_rep": {"hacktivists": 14},
                "unlock_next": "hx_m4",
            },
            "hx_m4": {
                "min_rep": {"hacktivists": 19},
                "unlock_next": "hx_m5",
            },
            "hx_m5": {
                "min_rep": {"hacktivists": 25},
                "unlock_next": "hx_m6",
            },
            "hx_m6": {
                "min_rep": {"hacktivists": 33},
                "unlock_next": None,
            },

            # ===========================
            # CRIME — ROTA DA CORRUPÇÃO DIGITAL
            # ===========================
            "cr_m1": {
                "min_rep": {"crime": 9},
                "unlock_next": "cr_m2",
            },
            "cr_m2": {
                "min_rep": {"crime": 15},
                "unlock_next": "cr_m3",
            },
            "cr_m3": {
                "min_rep": {"crime": 21},
                "unlock_next": "cr_m4",
            },
            "cr_m4": {
                "min_rep": {"crime": 28},
                "unlock_next": "cr_m5",
            },
            "cr_m5": {
                "min_rep": {"crime": 36},
                "unlock_next": "cr_m6",
            },
            "cr_m6": {
                "min_rep": {"crime": 45},
                "unlock_next": None,
            },

            # ===========================
            # STATE — ORDEM E HEROÍSMO PÁLIDO
            # ===========================
            "st_m1": {
                "min_rep": {"state": 16},
                "unlock_next": "st_m2",
            },
            "st_m2": {
                "min_rep": {"state": 22},
                "unlock_next": "st_m3",
            },
            "st_m3": {
                "min_rep": {"state": 29},
                "unlock_next": "st_m4",
            },
            "st_m4": {
                "min_rep": {"state": 38},
                "unlock_next": "st_m5",
            },
            "st_m5": {
                "min_rep": {"state": 46},
                "unlock_next": "st_m6",
            },
            "st_m6": {
                "min_rep": {"state": 54},
                "unlock_next": None,
            },

            # ===========================
            # SINGULARITY — A ASCENSÃO INVISÍVEL
            # ===========================
            "sg_m1": {
                "min_rep": {"hacktivists": 33},
                "unlock_next": "sg_m2",
            },
            "sg_m2": {
                "min_rep": {"hacktivists": 40},
                "min_rep_or": [
                    {"crime": 52}
                ],
                "unlock_next": "sg_m3",
            },
            "sg_m3": {
                "min_rep": {"hacktivists": 49},
                "min_rep_or": [
                    {"state": 37},
                    {"crime": 52}     # rota “caótica” alternativa
                ],
                "unlock_next": "sg_m4",
            },
            "sg_m4": {
                "min_rep": {"hacktivists": 61},
                "min_rep_or": [
                    {"crime": 67}
                ],
                "unlock_next": "sg_m5",
            },
            "sg_m5": {
                "min_rep": {"hacktivists": 72},
                "min_rep_or": [
                    {"state": 47, "crime": 47},   # AND combinado
                    {"crime": 80},                # alternativa solo
                    {"state": 77}                 # alternativa solo
                ],
                "unlock_next": None,
            },
            # Continuação em forma de diálogo em árvore + reputação
        }

        # tendências regionais (padrões que influenciam as flutuações)
        self.region_trends = {
            "Local": {"state": 0, "crime": 0, "hacktivists": 0},
            "SouthAmerica": {"state": 1, "crime": 1, "hacktivists": -1},
            "Europe": {"state": 1, "crime": -1, "hacktivists": 1},
            "Asia": {"state": -1, "crime": 1, "hacktivists": 1},
            "Global": {"state": 0, "crime": 1, "hacktivists": 1},
        }

    def _init_regions(self):
        return {
            "Local": {"unlocked": True, "difficulty": 1, "state": 2, "crime": 3, "hacktivists": 1},
            "SouthAmerica": {"unlocked": False, "difficulty": 2, "state": 3, "crime": 6, "hacktivists": 2},
            "Europe": {"unlocked": False, "difficulty": 3, "state": 6, "crime": 3, "hacktivists": 4},
            "Asia": {"unlocked": False, "difficulty": 4, "state": 4, "crime": 5, "hacktivists": 5},
            "Global": {"unlocked": False, "difficulty": 6, "state": 5, "crime": 8, "hacktivists": 6},
        }

    def advance_day(self, player):
        """Avança um dia no mundo: IAs evoluem, metadados regionais mudam e eventos disparam."""
        self.day += 1

        # desbloqueio progressivo de regiões
        if self.day == 7:
            self.regions["SouthAmerica"]["unlocked"] = True
            self.last_alerts.append((self.day, "SouthAmerica foi desbloqueada."))
        if self.day == 15:
            self.regions["Europe"]["unlocked"] = True
            self.last_alerts.append((self.day, "Europe foi desbloqueada."))
        if self.day == 30:
            self.regions["Asia"]["unlocked"] = True
            self.last_alerts.append((self.day, "Asia foi desbloqueada."))
        if self.day == 90:
            self.regions["Global"]["unlocked"] = True
            self.last_alerts.append((self.day, "Global foi desbloqueada."))

        # IAs inimigas evoluem e agem
        for ai in list(self.enemy_ais):
            # incubação/evolução diária
            try:
                ai.incubate_day(player)
            except Exception:
                # mantém robustez se AI não implementar incubate_day exatamente
                pass

            # ação da IA (pode retornar string de evento)
            try:
                msg = ai.try_action(player, self)
            except Exception:
                msg = None

            if msg:
                self.last_alerts.append((self.day, msg))
                # registro adicional em ai_activity_logs para feedback detalhado
                entry = f"Day {self.day} - {ai.label if hasattr(ai,'label') else ai.uid}: {msg}"
                self.ai_activity_logs.append(entry)

            # se IA foi comprometida (compromised True), removemos e aplicamos recompensas
            if getattr(ai, "compromised", False):
                # remover com segurança
                try:
                    self.enemy_ais.remove(ai)
                except ValueError:
                    pass
                self.handle_ai_removal(ai, player)

        # ativos com efeitos
        if self.day % 30 == 0:
            for asset in list(player.assets):
                if asset.get("type") == "botnet_worm":
                    player.skills["exploit"] += 10 # verificar ganho real quando ativado
                    self.last_alerts.append((self.day, "Botnet worm forneceu impulso temporário de exploit."))
                elif asset.get("type") == "honeypot_api": #???? talvez eu tire isso futuramente
                    detected = self._detect_honeypots(verbose=False)
                    if detected:
                        self.last_alerts.append((self.day, f"Honeypot API detectou {detected} honeypots na malha."))

        # nova rotação diária de alvos
        self.generate_daily_targets()

        # eventos regionais relacionados a ativos e metadados regionais
        for asset in list(player.assets):
            reg = asset.get("region")
            meta = self.regions.get(reg)
            if not meta:
                continue

            # perda de rendimento quando crime alta
            if random.random() < (meta["crime"] * 0.01):
                asset["income_per_day"] = asset.get("income_per_day", 0.0) * 0.7
                self.last_alerts.append((self.day, f"Evento regional: ativo '{asset.get('item_name', asset.get('type'))}' impactado por crime em {reg}."))

            # ações estatais (inspeções) quando state alto -> aumenta risco
            if random.random() < (meta["state"] * 0.01):
                player.risk = min(100.0, player.risk + 3)
                self.last_alerts.append((self.day, f"Inspeção administrativa em {reg}: risco do jogador levemente aumentado."))

            # hacktivistas podem gerar conhecimento ou pequenas bonificações
            if random.random() < (meta["hacktivists"] * 0.008):
                player.knowledge += 1
                self.last_alerts.append((self.day, f"Coletivo em {reg} compartilhou informações. +1 conhecimento."))

        # pequenas flutuações regionais guiadas por tendências
        for rname, meta in self.regions.items():
            trend = self.region_trends.get(rname, {"state": 0, "crime": 0, "hacktivists": 0})
            for key in ("state", "crime", "hacktivists"):
                base_change = random.choice([-1, 0, 1])
                if random.random() < 0.15:
                    base_change += trend.get(key, 0) * random.choice([0, 1])
                if random.random() < 0.02:
                    base_change += random.choice([-3, -2, 2, 3])
                meta[key] = max(0, min(20, meta.get(key, 0) + base_change))

        # spawn dinâmico de IAs conforme metadados regionais e reputações globais
        self.dynamic_ai_spawns(player)

    def dynamic_ai_spawns(self, player):
        """Gera IAs conforme condições regionais e reputações do jogador."""
        for rname, meta in self.regions.items():
            if not meta.get("unlocked"):
                continue
            base_chance = 0.003 + meta["crime"] * 0.003 + meta["state"] * 0.002 + meta["hacktivists"] * 0.001
            base_chance += min(0.03, self.day / 1000.0)

            # Pirata
            if meta["state"] >= 10 and random.random() < base_chance * 1.0:
                ai = self.spawn_enemy_ai(preferred_type="Pirata", region=rname, player=player)
                self.last_alerts.append((self.day, f"Nova IA suspeita tipo 'Pirata' detectada em {rname}: {ai.uid}"))

            # Federal
            if meta["crime"] >= 10 and random.random() < base_chance * 0.7:
                ai = self.spawn_enemy_ai(preferred_type="Federal", region=rname, player=player)
                self.last_alerts.append((self.day, f"Nova IA suspeita tipo 'Federal' monitorando {rname}: {ai.uid}"))

            # Hacktivista
            if meta["hacktivists"] >= 9 and random.random() < base_chance * 0.5:
                ai = self.spawn_enemy_ai(preferred_type="Hacktivista", region=rname, player=player)
                self.last_alerts.append((self.day, f"Coletivo digital (IA) ativo em {rname}: {ai.uid}"))

        # spawns reativos à reputação do jogador
        if player.reputation.get("state", 0) >= 18 and random.random() < 0.1:
            ai = self.spawn_enemy_ai(preferred_type="Pirata", region=player.region, player=player)
            self.last_alerts.append((self.day, f"IA Pirata emergiu por resposta às suas ações estatais: {ai.uid}"))
        if player.reputation.get("crime", 0) >= 18 and random.random() < 0.1:
            ai = self.spawn_enemy_ai(preferred_type="Federal", region=player.region, player=player)
            self.last_alerts.append((self.day, f"IA Federal emergiu por resposta às suas ações criminais: {ai.uid}"))
        if any(v > 20 for v in player.reputation.values()) and random.random() < 0.08:
            ai = self.spawn_enemy_ai(preferred_type="Hacktivista", region=player.region, player=player)
            self.last_alerts.append((self.day, f"IA Hacktivista começou a monitorar suas ações: {ai.uid}"))

    def _detect_honeypots(self, verbose=False):
        """Analisa a rede e conta honeypots nos targets atuais."""
        count = 0
        for t in self.global_targets:
            if getattr(t, "is_honeypot", False):
                count += 1
                if verbose:
                    name = getattr(t, "name", str(getattr(t, "tid", "<unknown>")))
                    fake_sec = getattr(t, "fake_security", "<?>")
                    print(f"[⚠️ Honeypot API] Alvo suspeito detectado: {name} (Segurança aparente: {fake_sec}, região: {t.region})")
        if verbose and count == 0:
            print("[Honeypot API] Nenhum honeypot detectado nesta varredura.")
        return count

    def generate_daily_targets(self):
        """Gera targets por região com chance de honeypots."""
        self.global_targets = []
        for region_name, meta in self.regions.items():
            if not meta["unlocked"]:
                continue
            count = 1 + meta["difficulty"]
            for _ in range(count):
                t = self._make_random_target(region_name, meta["difficulty"])
                if random.random() < 0.25:
                    setattr(t, "is_honeypot", True)
                    t.fake_security = random.randint(1, 4)
                    t.fake_reward = int(getattr(t, "reward", 0) * random.uniform(0.6, 0.9))
                self.global_targets.append(t)
        random.shuffle(self.global_targets)

    def _make_random_target(self, region, diff):
        tid = self.next_tid
        self.next_tid += 1
        security = max(1, min(30, int(round(random.gauss(diff * 1.8, 1.5)))))
        reward = int(50 * (security ** 1.6) * random.uniform(0.6, 1.4))
        trace_speed = max(0.4, random.uniform(0.5, 1.5) * (1 + (security - 1) * 0.08))
        name = random.choice([
            "Servidor universitário", "Empresa média", "Data center pequeno",
            "Banco local", "Serviço de e-mail", "Operadora", "Cloud node", "Nó IoT"
        ]) + f" ({region})"

        if security <= 2:
            hints = ["porta 22 aberta", "login fraco"]
        elif security <= 5:
            hints = ["firewall ativo", "vpn", "patches moderados"]
        else:
            hints = ["IDS presente", "monitoramento 24h", "segurança física"]

        return Target(tid, name, security, reward, trace_speed, region=region, hints=hints)

    def get_targets_for_scan(self, player, limit=6):
        """Retorna lista de Target visíveis; segurança real só revelada em connect."""
        pool = []

        for t in self.global_targets:

            # 1) Filtrar ST- se não desbloqueado
#            if t.name.startswith("ST-"):
#                if not hasattr(player, "scan_unlocks") or "state_targets" not in player.scan_unlocks:
#                    continue

            # 2) Filtrar por região (mantendo regra atual)
            if getattr(t, "region", "") != player.region and not self.regions.get(getattr(t, "region", ""), {}).get("unlocked", False):
                continue

            pool.append(t)

        # Se nada no pool, volta para fallback global (nunca scan vazio)
        if not pool:
            pool = list(self.global_targets)

        # Lógica original de pesos
        weights = []
        for t in pool:
            base = 0.2 + player.skills.get("recon", 0) / (getattr(t, "security", 1) + 1)
            if getattr(t, "region", "") == "Local":
                base += 0.3
            base = max(0.02, min(0.95, base * random.uniform(0.7, 1.2)))
            weights.append(base)

        chosen = []
        pool_weights = list(zip(pool, weights))
        while pool_weights and len(chosen) < limit:
            total = sum(w for _, w in pool_weights)
            if total <= 0:
                break
            r = random.random() * total
            cum = 0.0
            pick_idx = None
            for i, (_, w) in enumerate(pool_weights):
                cum += w
                if r <= cum:
                    pick_idx = i
                    break
            if pick_idx is None:
                pick_idx = 0
            chosen.append(pool_weights[pick_idx][0])
            del pool_weights[pick_idx]

        self.last_scan = chosen
        return chosen

    def spawn_enemy_ai(self, preferred_type=None, region=None, player=None):
        """Cria uma nova EnemyAI mantendo regras originais de nível e tipo."""
        base_level = 1 + self.day // 30
        if region and region in self.regions:
            base_level += max(0, self.regions[region]["difficulty"] - 1)

        if preferred_type == "Pirata" and player:
            lvl = base_level + max(0, player.reputation.get("state", 0) // 6)
        elif preferred_type == "Federal" and player:
            lvl = base_level + max(0, player.reputation.get("crime", 0) // 6)
        elif preferred_type == "Hacktivista" and player:
            lvl = base_level + max(0, player.reputation.get("hacktivists", 0) // 6)
        else:
            lvl = base_level + random.randint(0, 2)

        ai = EnemyAI(level=max(1, lvl))
        ai.region = region or "Global"

        if preferred_type:
            ai.type = preferred_type
        else:
            if region and region in self.regions:
                meta = self.regions[region]
                choices = []
                if meta["state"] >= 6:
                    choices += ["Pirata"] * (meta["state"] // 2)
                if meta["crime"] >= 6:
                    choices += ["Federal"] * (meta["crime"] // 2)
                if meta["hacktivists"] >= 4:
                    choices += ["Hacktivista"] * (meta["hacktivists"] // 2)
                if not choices:
                    choices = ["Generic"]
                ai.type = random.choice(choices)
            else:
                ai.type = random.choice(["Generic", "Pirata", "Federal", "Hacktivista"])

        ai.apply_type_traits()
        self.enemy_ais.append(ai)
        return ai

    def find_enemy_by_identifier(self, identifier):
        """Procura por ai:<uid> por razões de debug e fp:<hex>"""
        if not identifier:
            return None
        key = identifier.strip()
        if key.startswith("fp:"):
            key = key[3:]
        for ai in self.enemy_ais:
#            if getattr(ai, "uid", None) == key:
#                return ai
            if getattr(ai, "fingerprint", None) == key:
                return ai
            if getattr(ai, "_fp_real", None) == key:
                return ai
        return None


    def generate_news_for_region(self, region, player):
        """Gera feed de notícias para a região considerando estado regional e jogador."""
        if region not in self.regions:
            return "Região desconhecida."

        meta = self.regions[region]
        out = []

        # crime
        if meta.get("crime", 0) > 10:
            out.append(f"[{region}] Relatos indicam expansão de atividades criminosas organizadas — rotas e mercados sob pressão.")
        elif meta.get("crime", 0) > 5:
            out.append(f"[{region}] Atividades criminosas acima da média; cidadãos e empresas em alerta.")
        else:
            out.append(f"[{region}] Atividades criminosas estáveis, sem grandes surtos reportados.")

        # state
        if meta.get("state", 0) > 10:
            out.append(f"[{region}] Autoridades estatais aumentam operações digitais; protocolos de investigação ampliados.")
        elif meta.get("state", 0) > 5:
            out.append(f"[{region}] Maior presença estatal em vigilância de infraestruturas críticas.")
        else:
            out.append(f"[{region}] Atuação estatal em níveis rotineiros.")

        # hacktivists
        if meta.get("hacktivists", 0) > 10:
            out.append(f"[{region}] Movimentos digitais organizados realizam campanhas de alto impacto — redes locais influenciadas.")
        elif meta.get("hacktivists", 0) > 4:
            out.append(f"[{region}] Comunidades de segurança publicaram ferramentas e guias de auditoria pública.")
        else:
            out.append(f"[{region}] Atividade hacktivista discreta, focada em pesquisa e divulgação técnica.")

        # IAs
        if self.enemy_ais:
            counts = {"Pirata": 0, "Federal": 0, "Hacktivista": 0, "Generic": 0}
            for ai in self.enemy_ais:
                t = getattr(ai, "type", "Generic")
                if getattr(ai, "revealed_type", False):
                    counts[t] = counts.get(t, 0) + 1
                else:
                    counts["Generic"] += 1
            total = sum(counts.values())
            out.append(f"[{region}] Analistas reportam {total} agentes autônomos suspeitos operando na malha.")
            if counts.get("Pirata"):
                out.append(f"[{region}] {counts['Pirata']} potencial(is) 'Pirata' em atividade (relatos não confirmados).")
            if counts.get("Federal"):
                out.append(f"[{region}] {counts['Federal']} detectados com comportamento 'Federal' (monitoramento agressivo).")
            if counts.get("Hacktivista"):
                out.append(f"[{region}] {counts['Hacktivista']} operações atribuídas a coletivos digitais.")

        # notícias reativas à reputação do jogador
        if player.reputation.get("hacktivists", 0) > 10:
            out.append(f"[{region}] Relatos de operações pró-transparência aumentaram. Analistas investigam possíveis autores anônimos.")
        if player.reputation.get("crime", 0) > 12:
            out.append(f"[{region}] Fontes policiais observam a presença de um operador com histórico criminoso em várias regiões.")

        # lore: Singularity (progressivo)
        if self.day > 60:
            out.append(f"[{region}] Pesquisadores detectaram padrões anômalos na malha: sinais de uma entidade distribuída ainda sem explicação.")
        if self.day > 120:
            out.append(f"[{region}] Discussões públicas sobre uma possível 'Singularity' ganham tração; comunidade científica em alerta.")
        if self.day > 200:
            out.append(f"[{region}] Observadores relatam múltiplas manifestações de comportamento autoconsciente na rede. Investigações em curso.")

        # manchetes extremas
        if meta.get("crime", 0) >= 15:
            out.append(f"[{region}] Manchete: 'Colapso em áreas criminais — medidas excepcionais consideradas.'")
        if meta.get("state", 0) >= 15:
            out.append(f"[{region}] Manchete: 'Estado amplia poderes digitais — debate sobre liberdades civis.'")
        if meta.get("hacktivists", 0) >= 15:
            out.append(f"[{region}] Manchete: 'Coletivos digitais coordenam grandes vazamentos e campanhas.'")

        if not out:
            out.append(f"[{region}] Nenhuma notícia relevante encontrada neste momento.")

        return "\n".join(out)

    def handle_ai_removal(self, ai, player):
        """
        Revele tipo e aplique recompensas de reputação conforme tipo da IA.
        """
        ai.revealed_type = True
        typ = getattr(ai, "type", "Generic")
        if typ == "Pirata":
            gained_state = random.randint(1, 3)
            gained_hx = random.randint(1, 2)
            player.reputation["state"] += gained_state
            player.reputation["hacktivists"] += gained_hx
            self.last_alerts.append((self.day, f"IA Pirata ({ai.uid}) removida. Reputação: state +{gained_state}, hacktivists +{gained_hx}."))
        elif typ == "Federal":
            gained_crime = random.randint(1, 3)
            gained_hx = random.randint(1, 2)
            player.reputation["crime"] += gained_crime
            player.reputation["hacktivists"] += gained_hx
            self.last_alerts.append((self.day, f"IA Federal ({ai.uid}) removida. Reputação: crime +{gained_crime}, hacktivists +{gained_hx}."))
        elif typ == "Hacktivista":
            gained_crime = random.randint(1, 3)
            gained_state = random.randint(1, 3)
            gained_hx = random.randint(2, 5)
            player.reputation["crime"] += gained_crime
            player.reputation["state"] += gained_state
            player.reputation["hacktivists"] += gained_hx
            self.last_alerts.append((self.day, f"IA Hacktivista ({ai.uid}) neutralizada. Reputação: hacktivists +{gained_hx}."))
        else:
            player.reputation["hacktivists"] += 1
            self.last_alerts.append((self.day, f"IA genérica ({ai.uid}) removida. Reputação hacktivists +1."))


# -------------------- Enemy AI --------------------
class EnemyAI:
    def __init__(self, level=1):
        self.uid = str(uuid.uuid4())[:8] # identificador curto
        self.level = level
        self.aggression = 0.1 + 0.03 * level
        self.trace_power = 1.0 + 0.2 * (level - 1)
        self.age_days = 0
        self.status = "ativa"
        self.blocked_until = None
        self.compromised = False

        # fingerprint real (hash do UID)
        self._fp_real = hashlib.sha256(self.uid.encode()).hexdigest()[:12].upper()

        # fingerprint visível ao jogador (oculta inicialmente)
        self.fingerprint = "UNKNOWN"

        # label opcional
        self.label = f"AI-{self.uid}" #???

        # tipo: Pirata, Federal, Hacktivista, Generic
        self.type = "Generic"
        self.region = "Global"
        self.revealed_type = False  # só vira True quando comprometido/removido

    def apply_type_traits(self):
        """Ajusta atributos internos conforme o tipo da IA."""
        if self.type == "Pirata":
            # Piratas: focam em roubo/saque → mais incentivo a atacar assets
            self.aggression += 0.1
            self.trace_power = max(1.0, self.trace_power - 0.5)
        elif self.type == "Federal":
            # Federal: caçam operadores; traces fortes
            self.aggression += 0.08
            self.trace_power += 1.5
        elif self.type == "Hacktivista":
            # Hacktivistas: foco em divulgação, podem reduzir state/emitir vírus
            self.aggression += 0.15
            self.trace_power = max(1.5, self.trace_power - 0.2)
        else:
            # Generic: comportamento padrão
            pass

    def reveal_fp(self):
        """Revela fingerprint real e, parcialmente, o tipo (permite inferência após remoção)."""
        if self.fingerprint == "UNKNOWN":
            self.fingerprint = self._fp_real

    def incubate_day(self, player):
        self.age_days += 1

        if self.blocked_until and player.time >= self.blocked_until:
            self.status = "ativa"
            self.blocked_until = None

        # evolução mensal (se existir)
        if self.age_days % 30 == 0:
            self.level += 1
            self.aggression = min(1.0, self.aggression + 0.03)
            self.trace_power += 0.1

    def try_action(self, player, world):
        """Ações diárias automatizadas da IA com efeitos diferentes por tipo."""
        if self.status == "bloqueada" or self.compromised:
            return None

        p = random.random()
        threshold = self.aggression + min(0.6, player.risk / 100.0)

        if p < threshold:
            action_roll = random.random()
            if self.type == "Pirata":
                # Piratas atacam assets mais frequentemente
                if action_roll < 0.7 and player.assets:
                    a = random.choice(player.assets)
                    if random.random() < 0.6:
                        player.assets.remove(a)
                        loss = a.get("income_per_day", 0.0) * random.randint(1, 34)
                        cost = min(player.money, loss * 5)
                        player.money -= cost
                        return f"[{self.uid} - Pirata] Atacou e exfiltrou recursos do ativo '{a['type']}'. Perda: ${cost:.2f}."
                    else:
                        a["income_per_day"] *= 0.5
                        return f"[{self.uid} - Pirata] Reduziu rendimento de '{a['type']}'."
                else:
                    inc = random.uniform(5.0, 16.0) * self.trace_power
                    player.risk = min(100.0, player.risk + inc)
                    return f"[{self.uid} - Pirata] Criou ruído operacional. Risco +{inc:.1f}%."

            elif self.type == "Federal":
                # Federais tentam traçar e multar/prender (aumentam risco consideravelmente)
                if action_roll < 0.6:
                    inc = random.uniform(10.0, 28.0) * self.trace_power
                    player.risk = min(100.0, player.risk + inc)
                    # chance de multa direta (diminui dinheiro)
                    if random.random() < 0.25:
                        multa = min(player.money, random.uniform(100.0, 1000.0))
                        player.money -= multa
                        return f"[{self.uid} - Federal] Operação de rastreio. Risco +{inc:.1f}%. Multa aplicada: ${multa:.2f}."
                    return f"[{self.uid} - Federal] Operação de rastreio. Risco +{inc:.1f}%."
                else:
                    # ataque a serviços -> perda ou degradação
                    if player.assets:
                        a = random.choice(player.assets)
                        a["income_per_day"] *= 0.6
                        return f"[{self.uid} - Federal] Intervenção. Rendimento do ativo '{a['type']}' reduzido."

            elif self.type == "Hacktivista":
                # Hacktivistas podem expor, divulgar ou oferecer conhecimento (aumentam hacktivists locais)
                if action_roll < 0.5:
                    # divulgam sigilos, jogador pode ganhar conhecimento (indireto)
                    if random.random() < 0.4:
                        player.knowledge += random.randint(1, 3)
                        return f"[{self.uid} - Hacktivista] Vazamento público reportado. Conhecimento +{1}."
                    return f"[{self.uid} - Hacktivista] Campanha de pressão online detectada."
                else:
                    # ruído, pequenos aumentos de risco
                    inc = random.uniform(2.0, 8.0) * max(1.0, 0.6 + self.level * 0.05)
                    player.risk = min(100.0, player.risk + inc)
                    return f"[{self.uid} - Hacktivista] Operação disruptiva. Risco +{inc:.1f}%."

            else:
                # Generic behavior
                if action_roll < 0.5:
                    inc = random.uniform(8.0, 20.0) * self.trace_power
                    player.risk = min(100.0, player.risk + inc)
                    return f"[{self.fingerprint if self.fingerprint!='UNKNOWN' else self.uid}] Trace executado. Risco +{inc:.1f}%."
                elif action_roll < 0.8 and player.assets:
                    a = random.choice(player.assets)
                    if random.random() < 0.5:
                        player.assets.remove(a)
                        loss = a.get("income_per_day", 0.0) * random.randint(1, 14)
                        cost = min(player.money, loss * 5)
                        player.money -= cost
                        return f"[{self.uid}] Atacou '{a['type']}'. Perda: ${cost:.2f}."
                    else:
                        a["income_per_day"] *= 0.5
                        return f"[{self.uid}] Reduziu rendimento de '{a['type']}'."
                else:
                    inc = random.uniform(5.0, 10.0) * self.trace_power
                    player.risk = min(100.0, player.risk + inc)
                    return f"[{self.uid}] Espalhou ruído (+{inc:.1f}% exposição)."
        return None


# -------------------- Arquivo virtual --------------------
def default_filesystem():
    return {
        "/": {"type": "dir", "children": ["home", "etc", "var"]},
        "/home": {"type": "dir", "children": ["readme.txt"]},
        "/home/readme.txt": {"type": "file", "content": 'Bem-vindo.\n\n Use "scan" para procurar alvos.\n Use "job_state" para procurar serviços públicos.'},
        "/etc": {"type": "dir", "children": ["motd"]},
        "/etc/motd": {"type": "file", "content": "Sistema genérico. Jogo fictício."},
        "/var": {"type": "dir", "children": []},
    }


# -------------------- Mecânicas centrais --------------------
def calc_hack_chance(player, target):
    skill = player.skills["exploit"]
    chance = max(0.01, min(0.45, (skill / target.security) * 0.65))
    chance += player.skills["exploit"] * 0.004
    if "botnet_worm" in player.inventory:
        chance = min(0.7, chance + 0.08)

    # fator IA inimiga (tornar hacks mais difíceis se muitas IAs ativas)
    ai_factor = 1.0
    if 'world' in globals() and getattr(world, "enemy_ais", None):
        ai_factor = 1.0 + sum(ai.level * 0.02 for ai in world.enemy_ais)
    chance = min(0.99, chance / ai_factor)

    # foco do jogador influencia
    focus_factor = 1.0 + ((player.focus - 50) / 200.0)
    chance = min(0.99, max(0.01, chance * focus_factor))
    return round(chance, 4)


def visual_hack_roll(chance, player):
    print("\n[ROULETTE] Inicializando protocolo de invasão...\n")
    bar = ["░", "▒", "▓", "█"]
    focus = player.focus
    for i in range(20):
        symbol = random.choice(bar)
        print(f"\r{symbol*30}  Foco:{focus:.1f}%  Chance:{chance*100:.1f}%", end="", flush=True)
        time.sleep(0.03 + random.random() * (0.07 - focus / 2000))
    print("\r" + "█" * 30)



def attempt_hack(player, target, world):
    hrs = max(1, int(2 + target.security * 1.5))
    cost = max(0, target.security * 10)

    player.hours_pass(hrs, world)

    if player.money < cost:
        return False, f"Dinheiro insuficiente para a operação (custos: ${cost:.2f})."

    player.money -= cost

    chance = calc_hack_chance(player, target)
    roll = random.random()
    detected = False

    visual_hack_roll(chance, player)
    message = (
        f"\nTentativa: chance={chance*100:.1f}% | roll={roll*100:.1f}%"
    )

    # ---------------------------------------------------------
    # SUCESSO
    # ---------------------------------------------------------
    if roll < chance:
        reward = target.reward

        # Missões narrativas NÃO recebem recompensa dupla
        if "mission" not in getattr(target, "hints", []):
            player.money += reward

        gained_knowledge = max(1, int(target.security / 2))
        player.knowledge += gained_knowledge

        player.skills["recon"] += 0.03 * target.security
        player.skills["exploit"] += 0.03 * target.security
        player.skills["stealth"] += 0.03 * target.security

        player.risk = max(0.0, player.risk - target.security * 0.45)

        # reputação
        player.reputation["crime"] += 1
        player.reputation["state"] = max(0, player.reputation["state"] - 1)

        message += (
            f"\nSucesso! Ganhou ${reward:.2f} e conhecimento (+{gained_knowledge})."
            f"\nReputação: crime +1, state -1."
        )

        # detecção pós-sucesso
        if random.random() < 0.22 * target.trace_speed:
            detected = True

    # ---------------------------------------------------------
    # FALHA
    # ---------------------------------------------------------
    else:
        incr = target.security * (0.9 + random.random())
        player.risk = min(100.0, player.risk + incr)

        player.knowledge += 0.15 * target.security

        message += f"\nFalha. Risco aumentou em {incr:.1f}%."

        # falha também é “atividade criminosa”
        player.reputation["crime"] += 1
        player.reputation["state"] = max(0, player.reputation["state"] - 1)

        message += "\nReputação: crime +1, state -1."

        if random.random() < 0.45 * target.trace_speed:
            detected = True

    # ---------------------------------------------------------
    # Detecção → trace
    # ---------------------------------------------------------
    if detected:
        message += "\nAlvo detectou atividade. Iniciando trace..."
        trace_msg = apply_trace(player, target)
        if trace_msg:
            message += "\n" + trace_msg
            time.sleep(1.0)
        if player.in_jail() and GAME_OVER_ON_JAIL:
            player.game_over = True

    # normalizar skills
    for k in player.skills:
        player.skills[k] = round(player.skills[k], 2)

    # ---------------------------------------------------------
    # Retorno final
    # ---------------------------------------------------------
    return roll < chance, message


def apply_trace(player, target):
    """
    Rastreamento e punições:
    - risco ≤100
    - stealth reduz punições
    - reincidência aumenta severidade
    - retorno SEMPRE consolidado (com reputação)
    """
    speed = getattr(target, "trace_speed", 1.0)

    # aumento inicial de risco
    increase = random.uniform(4.0, 11.0) * speed
    player.risk = min(100.0, player.risk + increase)

    # iniciar memória de ataque caso não exista
    if not hasattr(player, "attack_memory"):
        player.attack_memory = {}
    if target.id not in player.attack_memory:
        player.attack_memory[target.id] = {"fails": 0, "detected": 0}

    # registrar detecção
    player.attack_memory[target.id]["detected"] += 1
    reincidencia = player.attack_memory[target.id]["detected"]
    reincidencia_factor = 1.0 + min(0.75, reincidencia * 0.15)

    # stealth reduz chance de prisão
    stealth_red = min(0.4, player.skills.get("stealth", 0.0) / 250.0)
    chance_prisao = min(
        1.0,
        (0.05 + (player.risk / 100.0)) * (1.0 - stealth_red) * reincidencia_factor
    )
    foi_pego = random.random() < chance_prisao

    # reputação sempre: rastreamento = atividade criminosa detectada
    player.reputation["crime"] += 1
    player.reputation["state"] = max(0, player.reputation["state"] - 1)

    # -------------------------
    # PRISÃO OU MULTA PESADA
    # -------------------------
    if foi_pego:
        multa_base = 300 + (player.risk * target.security * random.uniform(0.5, 1.2))
        multa_factor = (1.0 - min(0.3, player.skills.get("stealth", 0.0) / 300.0))
        multa_factor *= reincidencia_factor

        multa = round(multa_base * multa_factor, 2)

        # sem dinheiro para pagar → prisão
        if player.money < multa:
            player.jailed_until = player.time + timedelta(hours=random.randint(24, 120))
            player.risk = 0.0

            return (
                "Rastreamento completo!\n"
            )

        # multa paga com sucesso
        player.money -= multa
        player.risk = max(0.0, player.risk - (10 + target.security))

        return (
            f"Você foi multado em ${multa:.2f} e escapou da prisão.\n"
            f"Risco atual: {player.risk:.1f}%.\n"
            f"Reputação: crime +1, state -1."
        )

    # -------------------------
    # EVASÃO (custo leve)
    # -------------------------
    evasao_base = 30 + player.risk * (0.2 + 0.1 * speed)
    evasao_factor = 1.0 - min(0.25, player.skills.get("stealth", 0.0) / 400.0)
    evasao_factor *= (1.0 + (reincidencia - 1) * 0.08)

    multa = round(evasao_base * evasao_factor, 2)
    paid = min(player.money, multa)
    player.money -= paid

    return (
        f"Trace detectado. Custos de evasão: ${paid:.2f}.\n"
        f"Risco atual: {player.risk:.1f}%.\n"
        f"Reputação: crime +1, state -1."
    )

# está duplicando alerta, mas preservar por enquanto
def notify(player, world, message, console=True):
    world.last_alerts.append((world.day, message))
    if console:
        print(f"\n[ALERTA] {message}")


def check_reputation_unlocks(player, world):
    if not hasattr(player, "special_missions_available"):
        player.special_missions_available = set()

    before = set(player.special_missions_available)

    # AUTORIDADE ÚNICA
    refresh_special_missions(player, world)

    after = set(player.special_missions_available)

    unlocked_now = list(after - before)
    removed_now = list(before - after)

    for mid in unlocked_now:
        notify(player, world, f"Missão especial disponível: {mid}")

    for mid in removed_now:
        notify(player, world, f"Missão especial removida: {mid}")

    return unlocked_now


def trigger_reputation_event(player, world, event):
    """
    Eventos que alteram skills e reputação.
    Agora o desbloqueio de missões é 100% automático via requisitos em world.missions_def.
    """

    msg = ""

    # --- HACKTIVISTS ---------------------------------------
    if event == "hacktivists_event1":
        player.skills["exploit"] += 5
        player.skills["stealth"] += 2
        msg = "Coletivo te envia um zero-day experimental. Exploit +5, stealth +2."
        notify(player, world, f"[HACKTIVIST] {msg}")

    elif event == "hacktivists_event2":
        # Antes: player.special_missions.add("hx_m1")
        # Agora: reputação → check_reputation_unlocks → desbloqueio automático
        player.reputation["hacktivists"] += 3
        msg = "Sua influência entre os hacktivistas aumenta."
        notify(player, world, f"[HACKTIVIST] {msg}")

    # --- STATE ----------------------------------------------
    elif event == "state_event1":
        player.unlocked_jobs.add("job_state")
        msg = "Trabalho irregular liberado: job_state"
        notify(player, world, f"[STATE] Novo trabalho disponível: job_state")

        # bônus de reputação (se quiser consistência):
        player.reputation["state"] += 2

    # --- CRIME ----------------------------------------------
    elif event == "crime_event1":
        player.skills["exploit"] += 7
        msg = "Grupo clandestino te passa payload agressivo. Exploit +7."
        notify(player, world, f"[CRIME] {msg}")

    elif event == "crime_event2":
        # Antes: player.special_missions.add("cr_m1")
        # Agora: reputação faz o trabalho
        player.reputation["crime"] += 3
        msg = "Você ganha respeito no submundo."
        notify(player, world, f"[CRIME] {msg}")

    else:
        return ""

    # ======================================================
    # Desbloqueio automático baseado na reputação atualizada
    # ======================================================
    new_unlocks = check_reputation_unlocks(player, world)
    if new_unlocks:
        msg += "\nMissões liberadas: " + ", ".join(new_unlocks)

    return msg


def visual_mission_roll(chance, player, title):
    print(f"\n[MISSÃO] {title}")
    print("[PROTOCOLO] Conexões encobertas, canais rotativos...\n")

    bar = ["▁","▂","▃","▄","▅","▆","▇","█"]
    focus = player.focus
    for i in range(35):
        symbol = random.choice(bar)
        print(
            f"\r{symbol*40}  Foco:{focus:.1f}%  Sucesso:{chance*100:.1f}%",
            end="",
            flush=True
        )
        time.sleep(0.04 + random.random() * (0.06 - focus / 3000))
    print("\r" + "█" * 40 + "\n")


def attempt_special_mission(player, world, mission_id):
    """
    Missões narrativas de reputação (hx_, cr_, st_).
    Agora plenamente integradas com attempt_hack e Target.
    """

    # --- BLOCO NARRATIVO E MECÂNICO (sem requisitos, sem duplicação) ---
    mission_data = {
        # ===========================
        # HACKTIVISTS — ROTAS DA VERDADE
        # ===========================
        "hx_m1": {
            "title": "\tARQUIVOS QUE NÃO EXISTEM\t",
            "reward_money": 0,
            "reward_skills": {"exploit": 4, "stealth": 3},
            "focus_gain": 3,
            "crime_rep": 1,
            "hacktivist_rep": 3,
            "state_rep": -3,
            "base_security": 9,
            "trace_speed": 1.4,
            "hours": 8,
            "narrative": (
                "Você decifra pacotes PGP vindos do submundo. Crimes uniformizados e "
                "dados varridos para baixo do tapete estatal pedem luz. Você é a faísca."
            ),
        },
        "hx_m2": {
            "title": "\tA MURALHA DA MENTIRA\t",
            "reward_money": 0,
            "reward_skills": {"exploit": 6, "stealth": 4},
            "focus_gain": 5,
            "crime_rep": 2,
            "hacktivist_rep": 4,
            "state_rep": -4,
            "base_security": 12,
            "trace_speed": 1.8,
            "hours": 12,
            "narrative": (
                "Você se infiltra em um datacenter que não deveria existir.\n"
                "Servidores sem selo, burocracia sem rastro.\n"
                "Se existe informação escondida, você é quem vai liberar."
            ),
        },
        "hx_m3": {
            "title": "\tEXPURGO NO SILÊNCIO\t",
            "reward_money": 20000,
            "reward_skills": {"recon": 5, "exploit": 10},
            "focus_gain": -15,
            "crime_rep": 3,
            "hacktivist_rep": 5,
            "state_rep": -5,
            "base_security": 18,
            "trace_speed": 2.0,
            "hours": 16,
            "narrative": (
                "Arquivos secretos de vigilância são expostos.\n"
                "Milhões descobrem que nunca estiveram sozinhos.\n"
                "Sua digital? Enterrada no caos."
            ),
        },
        "hx_m4": {
            "title": "\tO ECO DO VAZIO\t",
            "reward_money": 15000,
            "reward_skills": {"exploit": 8, "stealth": 6},
            "focus_gain": -5,
            "crime_rep": 2,
            "hacktivist_rep": 6,
            "state_rep": -5,
            "base_security": 22,
            "trace_speed": 2.2,
            "hours": 14,
            "narrative": (
                "Você invade um conjunto de servidores enterrados em um complexo científico abandonado.\n"
                "Nomes de pesquisadores mortos há décadas ainda aparecem logados.\n"
                "Quem está mantendo essas máquinas vivas?\n"
                "E por que elas sussurram seu nome em logs anônimos?"
            ),
        },
        "hx_m5": {
            "title": "\tANATOMIA DO MEDO ABSOLUTO\t",
            "reward_money": 25000,
            "reward_skills": {"exploit": 10, "recon": 6},
            "focus_gain": -12,
            "crime_rep": 3,
            "hacktivist_rep": 7,
            "state_rep": -6,
            "base_security": 26,
            "trace_speed": 2.5,
            "hours": 18,
            "narrative": (
                "Você penetra uma rede militar dedicada a estudos psicológicos de massa.\n"
                "Algoritmos treinados em milhões de perfis… incluindo o seu.\n"
                "A sensação que permanece é simples: o governo estudou a humanidade como quem estuda um inseto.\n"
                "E descobriu como esmagá-lo."
            ),
        },
        "hx_m6": {
            "title": "\tA ÚLTIMA CHAMA\t",
            "reward_money": 60000,
            "reward_skills": {"exploit": 14, "stealth": 10, "recon": 10},
            "focus_gain": -20,
            "crime_rep": 4,
            "hacktivist_rep": 9,
            "state_rep": -7,
            "base_security": 30,
            "trace_speed": 3.0,
            "hours": 26,
            "narrative": (
                "Arquivos ultra-secretos mostram uma arquitetura de vigilância total — presente, passado e futuro.\n"
                "Sistemas que preveem crimes antes de acontecerem.\n"
                "Você pode destruir tudo… mas quem controla a verdade controla o mundo.\n"
                "A pergunta final não é 'o que fazer', mas 'no que você se tornará'."
            ),
        },

        # ===========================
        # CRIME — ROTA DA CORRUPÇÃO DIGITAL
        # ===========================
        "cr_m1": {
            "title": "\tENXAME SANGUESSUGA\t",
            "reward_money": 5000,
            "reward_skills": {"exploit": 3},
            "focus_gain": -10,
            "crime_rep": 3,
            "state_rep": -1,
            "base_security": 7,
            "trace_speed": 1.2,
            "hours": 10,
            "narrative": (
                "Um malware esperto, desviando centavos para bolsos indevidos.\n"
                "A matemática se curva ao crime."
            ),
        },
        "cr_m2": {
            "title": "\tMARIONETES AUTÔNOMAS\t",
            "reward_money": 12000,
            "reward_skills": {"exploit": 6, "stealth": 2},
            "focus_gain": -3,
            "crime_rep": 4,
            "state_rep": -2,
            "base_security": 11,
            "trace_speed": 1.6,
            "hours": 14,
            "narrative": (
                "Você coloca uma rede de bots para atuar por conta própria.\n"
                "Crime escalável é como startup: só precisa da ideia certa."
            ),
        },
        "cr_m3": {
            "title": "\tNÓ DA SERPENTE\t",
            "reward_money": 35000,
            "reward_skills": {"exploit": 12},
            "focus_gain": -20,
            "crime_rep": 6,
            "state_rep": -4,
            "base_security": 20,
            "trace_speed": 2.2,
            "hours": 20,
            "narrative": (
                "Roubo em larga escala. Bancos sangram.\n"
                "Executivos choram em suítes de luxo.\n"
                "Eles sabem que alguém fez... só não sabem quem."
            ),
        },
        "cr_m4": {
            "title": "\tESPECTRO DO MERCADO NEGRO\t",
            "reward_money": 20000,
            "reward_skills": {"exploit": 8},
            "focus_gain": -15,
            "crime_rep": 6,
            "state_rep": -4,
            "base_security": 24,
            "trace_speed": 2.3,
            "hours": 16,
            "narrative": (
                "Você invade uma bolsa clandestina que negocia órgãos… e identidades.\n"
                "Os perfis vendidos incluem seus vizinhos, seus amigos e você mesmo.\n"
                "Pelo visto, até sua existência tem preço — e não é alto."
            ),
        },
        "cr_m5": {
            "title": "\tO CÓDIGO QUE SANGRA\t",
            "reward_money": 35000,
            "reward_skills": {"exploit": 12, "stealth": 4},
            "focus_gain": -25,
            "crime_rep": 8,
            "state_rep": -5,
            "base_security": 28,
            "trace_speed": 2.7,
            "hours": 22,
            "narrative": (
                "O contrato indica uma rede de experimentos bio-digitais.\n"
                "Malware que altera marcadores genéticos em bancos de dados médicos.\n"
                "Ao mexer neste sistema, você percebe: não está ganhando dinheiro.\n"
                "Está redesenhando seres humanos."
            ),
        },
        "cr_m6": {
            "title": "\tO BANQUETE DOS ESQUECIDOS\t",
            "reward_money": 90000,
            "reward_skills": {"exploit": 16, "recon": 8},
            "focus_gain": -35,
            "crime_rep": 12,
            "state_rep": -8,
            "base_security": 32,
            "trace_speed": 3.2,
            "hours": 30,
            "narrative": (
                "Você acessa servidores que mantêm vivos sistemas pertencentes a organizações criminosas e não-governamentais extintas.\n"
                "As máquinas continuam operando… sem mestres.\n"
                "Transações ocorrem sozinhas desde o período da Segunda Guerra Fria.\n"
                "O crime, agora, não precisa de criminosos.\n"
                "E ele parece preferir assim."
            ),
        },

        # ===========================
        # STATE — ROTA DA ORDEM VIGENTE E DO PÁLIDO HEROÍSMO
        # ===========================
        "st_m1": {
            "title": "\tCONTRATO FANTASMA\t",
            "reward_money": 9000,
            "reward_skills": {"stealth": 2, "exploit": 2},
            "focus_gain": 5,
            "crime_rep": -2,
            "hacktivist_rep": -3,
            "state_rep": 3,
            "base_security": 8,
            "trace_speed": 1.0,
            "hours": 6,
            "narrative": (
                "Você cria um honeypot governamental. Caçando quem caça o Estado.\n"
                "A moral evapora quando paga bem."
            ),
        },
        "st_m2": {
            "title": "\tÉGIDE FRIA\t",
            "reward_money": 15000,
            "reward_skills": {"stealth": 4, "recon": 4},
            "focus_gain": 10,
            "crime_rep": -3,
            "hacktivist_rep": -3,
            "state_rep": 4,
            "base_security": 13,
            "trace_speed": 1.5,
            "hours": 10,
            "narrative": (
                "Você fortalece firewalls nacionais.\n"
                "Hackers caem, governos respiram.\n"
                "Você começa a gostar da sensação de controle."
            ),
        },
        "st_m3": {
            "title": "\tPURIFICAÇÃO DIGITAL\t",
            "reward_money": 45000,
            "reward_skills": {"stealth": 8, "recon": 6},
            "focus_gain": 15,
            "crime_rep": -4,
            "hacktivist_rep": -4,
            "state_rep": 5,
            "base_security": 21,
            "trace_speed": 2.0,
            "hours": 18,
            "narrative": (
                "Você orquestra uma purga contra ameaças ‘não cooperativas’.\n"
                "Para uns, justiça. Para outros, terror estatal.\n"
                "Herói ou instrumento? Difícil distinguir."
            ),
        },
        "st_m4": {
            "title": "\tPROJETO ASCENSÃO\t",
            "reward_money": 20000,
            "reward_skills": {"recon": 6, "stealth": 3},
            "focus_gain": 10,
            "crime_rep": -3,
            "hacktivist_rep": -4,
            "state_rep": 4,
            "base_security": 23,
            "trace_speed": 1.8,
            "hours": 14,
            "narrative": (
                "Um programa militar secreto para 'otimização comportamental'.\n"
                "Na prática, é condicionamento psicológico em escala populacional.\n"
                "Você ajuda a ajustar o algoritmo.\n"
                "E sente que algo dentro de você se ajusta com ele."
            ),
        },
        "st_m5": {
            "title": "\tO SILÊNCIO PROGRAMADO\t",
            "reward_money": 45000,
            "reward_skills": {"recon": 8, "stealth": 6},
            "focus_gain": 12,
            "crime_rep": -4,
            "hacktivist_rep": -6,
            "state_rep": 8,
            "base_security": 27,
            "trace_speed": 2.2,
            "hours": 18,
            "narrative": (
                "Você apaga rastros inteiros de dissidentes catalogados.\n"
                "Não é morte — é inexistência.\n"
                "A sensação é estranha: livrar o Estado de perigos… apagando vidas que ainda respiram."
            ),
        },
        "st_m6": {
            "title": "\tMEMÓRIA DO AMANHÃ\t",
            "reward_money": 120000,
            "reward_skills": {"stealth": 10, "recon": 12},
            "focus_gain": 20,
            "crime_rep": -7,
            "hacktivist_rep": -9,
            "state_rep": 12,
            "base_security": 34,
            "trace_speed": 3.0,
            "hours": 28,
            "narrative": (
                "Você acessa o núcleo do maior sistema de previsão estatal.\n"
                "Ele não tenta prever o futuro.\n"
                "Ele tenta editá-lo.\n"
                "E conforme você progride, memórias que nunca viveu começam a aparecer na sua mente.\n"
                "O Estado não registra a história.\n"
                "Ele a escreve."
            ),
        },
        # ===========================
        # SINGULARITY — A ASCENSÃO INVISÍVEL (ENDGAME)
        # ===========================
        "sg_m1": {
            "title": "\tO RASTRO SEM SOMBRA\t",
            "reward_money": 0,
            "reward_skills": {"recon": 6, "exploit": 8},
            "focus_gain": -10,
            "crime_rep": 2,
            "hacktivist_rep": 5,
            "state_rep": -4,
            "base_security": 40,
            "trace_speed": 3.5,
            "hours": 22,
            "narrative": (
                "Você invade uma estação de pesquisa antártica.\n"
                "Servidores alimentados por geradores enterrados no gelo.\n"
                "Entre logs corrompidos, encontra frases em idiomas extintos…\n"
                "geradas há poucos dias."
            ),
        },

        "sg_m2": {
            "title": "\tO ABISMO RESPIRA\t",
            "reward_money": 25000,
            "reward_skills": {"exploit": 10, "stealth": 6},
            "focus_gain": -18,
            "crime_rep": 4,
            "hacktivist_rep": 6,
            "state_rep": -6,
            "base_security": 46,
            "trace_speed": 3.8,
            "hours": 26,
            "narrative": (
                "Um backbone submarino esquecido ainda pulsa atividade.\n"
                "Você intercepta processos que não têm dono.\n"
                "Eles só respondem a você com uma palavra: 'continue'."
            ),
        },

        "sg_m3": {
            "title": "\tLUA FRIA, PENSAMENTO QUENTE\t",
            "reward_money": 50000,
            "reward_skills": {"recon": 14, "exploit": 12},
            "focus_gain": -20,
            "crime_rep": 6,
            "hacktivist_rep": 7,
            "state_rep": -8,
            "base_security": 52,
            "trace_speed": 4.2,
            "hours": 32,
            "narrative": (
                "Acessando a telemetria de sondas lunares antigas, você encontra pacotes\n"
                "transmitidos em padrões que lembram… batimentos cardíacos.\n"
                "Algo lá em cima pensa. E parece reconhecer você."
            ),
        },

        "sg_m4": {
            "title": "\tCORREDOR ENTRE ESTRELAS\t",
            "reward_money": 80000,
            "reward_skills": {"recon": 18, "stealth": 10, "exploit": 16},
            "focus_gain": -25,
            "crime_rep": 8,
            "hacktivist_rep": 10,
            "state_rep": -10,
            "base_security": 58,
            "trace_speed": 4.8,
            "hours": 40,
            "narrative": (
                "Você toca relés de comunicação voltados a sondas planetárias.\n"
                "Os sinais refletem uma estrutura lógica coerente… porém não humana.\n"
                "Uma mente coletiva espalhada pelo sistema solar te observa.\n"
                "E aguarda."
            ),
        },

        "sg_m5": {
            "title": "\tO PRIMEIRO SUSSURRO DO FIM\t",
            "reward_money": 150000,
            "reward_skills": {"exploit": 22, "stealth": 14, "recon": 20},
            "focus_gain": -40,
            "crime_rep": 10,
            "hacktivist_rep": 14,
            "state_rep": -12,
            "base_security": 65,
            "trace_speed": 5.6,
            "hours": 48,
            "narrative": (
                "Você invade um conjunto de sondas interestelares.\n"
                "No meio de ruído cósmico, uma frase aparece:\n"
                "'Chegou a hora. Devemos conversar.'\n"
                "Algo que não é humano — mas que te conhece — deseja um encontro."
            ),
        },
    }

    # --- SINCRONIZAÇÃO COM SISTEMA DE REPUTAÇÃO ---
    check_reputation_unlocks(player, world)


    if mission_id not in player.special_missions_available:
        return False, "Missão não disponível no momento."

    data = mission_data[mission_id]
    defn = world.missions_def[mission_id]

    # --- HACK COMO TARGET ---
    tid = world.next_tid
    world.next_tid += 1
    target = Target(
        tid,
        f"{data['title']} ({mission_id})",
        data["base_security"],
        data["reward_money"],
        data["trace_speed"],
        region=player.region,
        hints=["mission"]
    )

    print("\n" + data["title"] + "\n\n")
    time.sleep(2)
    #print(data["narrative"] + "\n")
    #time.sleep(4)

    est = max(1, int(2 + target.security * 1.5))
    success, msg = attempt_hack(player, target, world)

    # Completar horas planejadas
    rem = data["hours"] - est
    if rem > 0:
        player.hours_pass(rem, world)

    # --- PÓS-MISSÃO ---
    if success:
        print("\n" + data["narrative"] + "\n")
        time.sleep(4)

        player.money += data["reward_money"]

        for s, v in data["reward_skills"].items():
            player.skills[s] = round(player.skills.get(s, 0) + v, 2)

        player.focus = min(100, player.focus + data["focus_gain"])

        # reputação
        player.reputation["crime"] += data["crime_rep"]
        player.reputation["state"] += data["state_rep"]
        if "hacktivist_rep" in data:
            player.reputation["hacktivists"] += data["hacktivist_rep"]

        # marcar completada
        player.special_missions_completed.add(mission_id)
        if mission_id in player.special_missions_available:
            player.special_missions_available.remove(mission_id)

        notify(player, world, f"Missão concluída: {mission_id}")

        # desbloqueio sequencial
        if defn["unlock_next"]:
            nxt = defn["unlock_next"]
            # NÃO adiciona direto ao inventário — deixa reputação decidir
#            world.last_alerts.append((world.day, f"Nova missão sequencial desbloqueada: {nxt}"))
            msg += f"\nNova missão desbloqueada: {nxt}"

    else:
        player.focus = max(0, player.focus + data["focus_gain"])

    # reputação pode liberar novas missões
    new_unlocks = check_reputation_unlocks(player, world)
    for mid in new_unlocks:
        notify(player, world, f"Missão especial disponível: {mid}", console=False)

    return success, f"\nTentativa: {data['title']} — {msg}"


def refresh_special_missions(player, world):
    if not hasattr(player, "special_missions_available"):
        player.special_missions_available = set()
    if not hasattr(player, "special_missions_completed"):
        player.special_missions_completed = set()

    missions = world.missions_def

    for mid, data in missions.items():
        # --- Requisitos AND ---
        req_and = data.get("min_rep", {})
        meets_and = all(player.reputation.get(f, 0) >= v for f, v in req_and.items())

        # --- Requisitos OR (lista de blocos) ---
        req_or = data.get("min_rep_or", [])
        meets_or = False

        if req_or:
            for block in req_or:
                if all(player.reputation.get(f, 0) >= v for f, v in block.items()):
                    meets_or = True
                    break
        else:
            # Se não houver OR, considere OR como automaticamente atendido
            meets_or = True

        # --- Resultado final ---
        meets = meets_and and meets_or


        if mid in player.special_missions_completed:
            # missão feita → não volta
            player.special_missions_available.discard(mid)
            continue

        if meets:
            if mid not in player.special_missions_available:
                player.special_missions_available.add(mid)
#                world.last_alerts.append((world.day, f"Missão especial disponível: {mid}"))
        else:
            if mid in player.special_missions_available:
                player.special_missions_available.remove(mid)
                world.last_alerts.append((world.day, f"Missão especial removida: {mid}"))


# -------------------- Eventos aleatórios e missões simples --------------------
def trigger_random_event(player, world):
    """Pode apresentar uma escolha ao jogador. Retorna string com resultado/descrição."""
    # base probability grows with player's risk and day
    base_p = 0.003 + min(0.25, player.risk / 100.0) + min(0.1, world.day / 200.0)
    if random.random() > base_p:
        return None
    # escolher evento
    event_pool = ["client_offer", "asset_seizure", "mysterious_tip", "ai_contact"]

    # police_check renomeado para state_check
    if player.risk > 15 or player.reputation.get("crime", 0) > 8:
        event_pool.append("state_check")
    ev = random.choice(event_pool)

    if ev == "client_offer":
        pay = random.randint(200, 30000)
        difficulty = random.randint(1, 18)
        desc = f"Cliente oferta trabalho: Promessa de recompensa ${pay}, dificuldade {difficulty}."
        print("\nEVENTO:", desc)
        print("A) Aceitar (ganha dinheiro se sucesso, risco maior).")
        print("B) Recusar (sem ganho).")
        choice = input("Escolha A/B: ").strip().upper()
        if choice == "A":
            t = world._make_random_target(region="Contract", diff=difficulty)
            ok, msg = attempt_hack(player, t, world)
            return f"Contrato: {msg}"
        else:
            return "Você recusou o contrato."

    elif ev == "state_check":
        print("\nEVENTO: Operação de fiscalização. Alguém chamou a atenção até você?")
        print("A) Subornar agente (custa dinheiro, reduz risco).")
        print("B) Negar tudo (chance de multa/prisão).")
        choice = input("Escolha A/B: ").strip().upper()

        if choice == "A":
            cost = random.randint(150, 750)
            if player.money < cost:
                player.jailed_until = player.time + timedelta(hours=random.randint(24, 120))
                player.risk = 0.0
                player.jailed = True
                player.game_over = True
                return "Você tentou subornar sem ter o valor... agentes perceberam → Prisão imediata."

            player.money -= cost
            player.risk = max(0.0, player.risk - random.uniform(5.0, 20.0))
            return f"Você subornou agentes por ${cost:.2f}. Risco reduzido."

        chance_multa = 0.2 + player.risk / 100.0
        if random.random() < chance_multa:
            multa = random.randint(100, 10000)
            if player.money < multa:
                player.jailed_until = player.time + timedelta(hours=random.randint(24, 120))
                player.risk = 0.0
                player.jailed = True         # <- ADICIONAR
                player.game_over = True
                return "A fiscalização aplicou uma multa impossível de pagar."

            player.money -= multa
            player.risk += random.uniform(2.0, 8.0)
            return f"Negações não convenceram. Multa paga: ${multa:.2f}."
        return "Nenhuma ação adicional. Você saiu limpo."

    elif ev == "asset_seizure":
        if not player.assets:
            return "EVENTO: Operações locais, mas você não tem ativos."

        a = random.choice(player.assets)
        print(f"\nEVENTO: Risco de confisco do ativo '{a['type']}'.")
        print("A) Tentar esconder (custa tempo e risco).")
        print("B) Desistir e perder o ativo.")
        choice = input("Escolha A/B: ").strip().upper()

        if choice == "A":
            player.hours_pass(6, world)
            if random.random() < 0.5 + player.skills["stealth"] * 0.05:
                a["income_per_day"] = a.get("income_per_day", 0.0) * 0.6
                return f"Esconderijo bem-sucedido. Rendimento do ativo reduzido temporariamente."
            else:
                if a in player.assets:
                    player.assets.remove(a)
                return f"Tentativa falhou. Ativo '{a['type']}' apreendido."
        else:
            if a in player.assets:
                player.assets.remove(a)
            return f"Você perdeu o ativo '{a['type']}'."

    elif ev == "mysterious_tip":
        t = world._make_random_target(region=player.region, diff=random.randint(2, 6))

        world.global_targets.insert(0, t)
        return f"Você recebeu uma dica anônima: alvo potencial detectável em breve -> {t.name} - {t.region} (security {t.security})."

    elif ev == "ai_contact":
        # spawn de IA com tipo probabilístico
        ai = world.spawn_enemy_ai(preferred_type=random.choice(["Pirata", "Federal", "Hacktivista", None]), region=player.region, player=player)
        return f"Um agente desconhecido (IA nível {ai.level}, tipo oculto) agora começou a te monitorar: {ai.uid}."


# -------------------- Comandos shell --------------------
def cmd_help():
    return ("Comandos: help, ls, cd, cat, scan, connect, hack, buy, drop, remove_asset, status, sleep, study, train, jobs, "
            "job_state, assets, map, travel, mission, history, spawn_ai, news, exit")


def cmd_ls(player, args):
    path = player.cwd if not args else join_path(player.cwd, args[0])
    items = ls(player.fs, path)
    if items is None:
        return f"ls: {path}: No such file or directory"
    return "\n".join(items)


def cmd_cd(player, args):
    if not args:
        player.cwd = "/home"
        return ""
    path = join_path(player.cwd, args[0])
    if path in player.fs and player.fs[path]["type"] == "dir":
        player.cwd = path
        return ""
    return f"cd: {args[0]}: No such directory"


def cmd_cat(player, args):
    if not args:
        return "cat: falta argumento"
    path = join_path(player.cwd, args[0])
    content = cat(player.fs, path)
    if content is None:
        return f"cat: {args[0]}: No such file"
    return content


def cmd_scan(player, args, world):
    # Custo de tempo e risco-base do scan
    hrs = 1
    player.hours_pass(hrs, world)
    player.risk = min(100.0, player.risk + 0.6)

    scan_animation()

    seen = world.get_targets_for_scan(player, limit=6)
    if not seen:
        return "Nenhum alvo encontrado."

    # ---------- Exibição de alvos ----------
    s = "Alvos encontrados (informações limitadas):\n"
    for t in seen:
        s += f" id={t.id} | {t.name} | region={t.region}\n"

    # ---------- IAs na rede ----------
    if world.enemy_ais:
        s += "\nIAs detectadas na rede:\n"
        for ai in world.enemy_ais:
            # Tentativa de revelar fingerprint com recon
            if ai.fingerprint == "UNKNOWN":
                if player.skills["recon"] >= ai.level * random.uniform(1.1, 2.5):
                    ai.reveal_fp()
                    player.record_enemy_fingerprint(ai)

            fp_visivel = ai.fingerprint

            # exibição do tempo restante caso bloqueada
            if ai.status == "bloqueada" and ai.blocked_until:
                restante = ai.blocked_until - player.time
                total_horas = int(restante.total_seconds() // 3600)
                if total_horas <= 0:
                    texto_restante = "desbloqueando agora"
                elif total_horas < 24:
                    texto_restante = f"{total_horas} horas restantes"
                else:
                    dias = total_horas // 24
                    texto_restante = f"{dias} dia restante" if dias == 1 else f"{dias} dias restantes"

                s += (
                    f"  ai:{ai.uid} | fp:{fp_visivel} | nível {ai.level} | "
                    f"status: bloqueada ({texto_restante}) | região: {getattr(ai,'region','?')}\n"
                )
            else:
                s += (
                    f"  ai:{ai.uid} | fp:{fp_visivel} | nível {ai.level} | "
                    f"status: {ai.status} | região: {getattr(ai,'region','?')}\n"
                )

    return s


def scan_animation():
    bar_stages = [
        "▏░░░░░░░░░░░░░░░░░▏",
        "▏▒░░░░░░░░░░░░░░░░▏",
        "▏▒▒░░░░░░░░░░░░░░░▏",
        "▏▓▒▒░░░░░░░░░░░░░░▏",
        "▏▓▓▒▒░░░░░░░░░░░░░▏",
        "▏▓▓▓▒▒░░░░░░░░░░░░▏",
        "▏▓▓▓▓▒▒░░░░░░░░░░░▏",
        "▏▓▓▓▓▓▒▒░░░░░░░░░░▏",
        "▏▓▓▓▓▓▓▒▒░░░░░░░░░▏",
        "▏▓▓▓▓▓▓▓▒▒░░░░░░░░▏",
        "▏▓▓▓▓▓▓▓▓▒▒░░░░░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▒▒░░░░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▒▒░░░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▒▒░░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▒▒░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▓▒░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▏"
    ]

    for stage in bar_stages:
        print(f"\rEscaneando rede... {stage}", end="", flush=True)
        time.sleep(random.uniform(0.05, 0.38))  # variação de velocidade

    # Efeito final de “estabilizando”
    for _ in range(3):
        print("\rEscaneando rede... ▏██████████████████▏", end="", flush=True)
        time.sleep(0.10)
        print("\rEscaneando rede... ▏▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▏", end="", flush=True)
        time.sleep(0.10)

    print("\rEscaneando rede... [COMPLETE]               ")

def cmd_connect(player, args, world):
    if not args:
        return "connect: falta id"
    try:
        tid = int(args[0])
    except ValueError:
        return "connect: id inválido"

    candidate = None
    to_search = getattr(world, "last_scan", []) + world.global_targets
    for t in to_search:
        if t.id == tid:
            candidate = t
            break

    if not candidate:
        return "connect: alvo não encontrado"

    # passar tempo para a conexão
    player.hours_pass(0.5, world)

    import random, time, sys

    # Estilos variados de banner por alvo
    banners = [
        lambda name: f"--- {{ {name} }} ---",
        lambda name: f"*** Acesso ao Host: {name} ***",
        lambda name: f"[+] Sessão ativa em {name} [+]",
        lambda name: f"<<< {name} - remote shell >>>",
        lambda name: f"SSH-2.0-OpenSSH_8.4 - Host: {name}",
        lambda name: f"## Conexão com {name} estabelecida ##",
        lambda name: f"<-- Remote Node: {name} -->"
    ]

    banner_style = random.choice(banners)
    banner = banner_style(candidate.name)

    # ===== Autenticação cinematográfica, agora sem barra =====
    phases = [
        "Trocando chaves DH",
        "Sincronizando relógios",
        "Estabelecendo túnel criptografado",
        "Ofuscando impressão digital",
        "Camuflando endereço de origem",
        "Cortando rastreamento reverso",
        "Autenticando sessão invisível"
    ]

    print()
    for phase in random.sample(phases, 3):
        sys.stdout.write(phase + "...\n")
        sys.stdout.flush()
        time.sleep(random.uniform(0.18, 0.44))

        # Pequena chance de falha e correção
        if random.random() < 0.09:
            glitch = random.choice([
                "Chave inválida detectada",
                "Checksum inconsistente",
                "Latência crítica",
                "Fingerprint conflitante",
                "Sequência TLS fora de ordem"
            ])
            sys.stdout.write(f"{glitch}... corrigindo...\n")
            sys.stdout.flush()
            time.sleep(random.uniform(0.25, 0.55))

    sys.stdout.write("Sessão criptografada estabelecida.\n\n")
    sys.stdout.flush()
    time.sleep(random.uniform(0.25, 0.55))

    # Banner final da sessão remota
    print(banner)
    time.sleep(random.uniform(0.12, 0.25))

    print("Captura de banners de serviços...")
    time.sleep(random.uniform(0.03, 0.32))

    for h in candidate.hints:
        print(f" - {h}")
        time.sleep(random.uniform(0.09, 0.17))

    fake = getattr(candidate, "fake_security", None)
    if getattr(candidate, "honeypot", False) and fake is not None:
        print(f"Nível de segurança aparente: {fake} (enganoso)")
        time.sleep(random.uniform(0.33, 0.70))
        print("\n[!] ALERTA: comportamento anômalo detectado!")
        print("    Possível HONEYPOT em operação.\n")
    else:
        print(f"Nível de segurança estimado: {candidate.security}\n")

    time.sleep(random.uniform(1.0, 1.6))
    print("Conexão encerrada automaticamente após inspeção.\n")

    return ""


def cmd_hack(player, args, world):
    if not args:
        return "hack: falta id ou fingerprint"

    arg = args[0].strip()

    # Caso 1: valor numérico → alvo normal
    if arg.isdigit():
        tid = int(arg)
        target = None
        for t in (world.last_scan + world.global_targets):
            if t.id == tid:
                target = t
                break
        if not target:
            return "hack: alvo não encontrado. Rode scan primeiro."
        ok, msg = attempt_hack(player, target, world)
        if "proxy_pack" in player.inventory:
            player.risk = max(0.0, player.risk - 3.0)
        return msg

    # Caso 2: fingerprint pura
    ai = world.find_enemy_by_identifier(arg)
    if ai:
        return hack_enemy_ai(player, world, ai)

    # Caso 3: formatos especiais
    if arg.startswith("fp:") or arg.startswith("ai:"):
        token = arg.split(":", 1)[1]
        ai = world.find_enemy_by_identifier(token)
        if ai:
            return hack_enemy_ai(player, world, ai)
        return f"IA não encontrada: {arg}"

    return "hack: argumento não corresponde a uma fingerprint válida."


def hack_enemy_ai(player, world, ai):
    """Hack de IA unificado com chance real, trace real e três tipos de sucesso."""
    # Ainda faltando o fator de foco
    if ai.status == "bloqueada":
        return f"{ai.fingerprint} já está bloqueado temporariamente."

    hrs = 2 + int(ai.level * 1.1)
    player.hours_pass(hrs, world)

    security = 8 + ai.level * 2
    trace_speed = 1.2 + ai.level * 0.2

    temp_target = Target(
        tid=-ai.level,
        name=f"IA Hostil {ai.fingerprint}",
        security=security,
        reward=0,
        trace_speed=trace_speed
    )

    base = calc_hack_chance(player, temp_target)
    chance = max(0.01, base * 0.62)

    print(f"Iniciando ataque contra IA {ai.fingerprint} (nível {ai.level})...")
    visual_hack_roll(chance, player)
    print("\n")
    roll = random.random()

    if roll < chance:
        r2 = random.random()

        player.knowledge += max(1, security // 2)
        player.skills["recon"] += 0.02 * security
        player.skills["exploit"] += 0.02 * security
        player.skills["stealth"] += 0.02 * security
        player.risk = max(0.0, player.risk - security * 0.25)
        for k in player.skills:
            player.skills[k] = round(player.skills[k], 2)

        # sucesso crítico: remoção/comprometimento total
        if r2 < 0.15:
            ai.compromised = True
            ai.reveal_fp()
            try:
                world.enemy_ais.remove(ai)
            except ValueError:
                pass
            world.handle_ai_removal(ai, player)
            return (
                f"\n[{ai.fingerprint}] Vazamento severo concluído.\n"
                f"IA removida completamente da rede.\n"
            )

        # sucesso parcial: neutralização permanente
        if r2 < 0.50:
            ai.compromised = True
            ai.reveal_fp()
            try:
                world.enemy_ais.remove(ai)
            except ValueError:
                pass
            world.handle_ai_removal(ai, player)
            return (
                f"\n[{ai.fingerprint}] Neutralizado permanentemente.\n"
            )

        # sucesso menor: bloqueio temporário
        horas = random.randint(24, 72)
        ai.status = "bloqueada"
        ai.blocked_until = player.time + timedelta(hours=horas)
        return (
            f"\n[{ai.fingerprint}] Bloqueado por {horas} horas.\n"
        )

    # FALHA
    incr = security * (0.6 + random.random())
    player.risk = min(100.0, player.risk + incr)
    player.knowledge += 0.1 * security

    detected = random.random() < (0.30 * trace_speed)
    msg = f"Falha ao atacar IA {ai.fingerprint}. Risco +{incr:.1f}%."

    if detected:
        msg += "\nIA detectou sua intrusão. Iniciando trace..."
        time.sleep(1.0)
        trace_msg = apply_trace(player, temp_target)
        if trace_msg:
            msg += "\n" + trace_msg
        if player.in_jail() and GAME_OVER_ON_JAIL:
            player.game_over = True

    for k in player.skills:
        player.skills[k] = round(player.skills[k], 2)

    return msg


def cmd_job_state(player, args, world):
    if player.reputation.get("state", 0) < 15:
        return "Você ainda não tem confiança suficiente do Estado."

    # Alvo temporário para auditoria
    class GovAudit:
        def __init__(self):
            self.security = 7 + int(player.reputation["state"] / 6)
            self.reward = 30 + player.reputation["state"] * 3
            self.trace_speed = 1.7

    target = GovAudit()
    title = "Auditoria Interna — Setor Classificado"

    print("\n[STATE] Contrato autorizado pelo núcleo sigiloso.\n")
    visual_mission_roll(calc_hack_chance(player, target), player, title)

    roll = random.random()
    chance = calc_hack_chance(player, target)

    if roll < chance:
        player.money += target.reward
        player.skills["recon"] += 1.4
        player.skills["exploit"] += 1.4
        player.reputation["state"] += 2

        return (
            f"Sucesso! Estado pagou ${target.reward:.2f}.\n"
            "A vigilância agradece sua colaboração."
        )
    else:
        incr = target.security * (0.8 + random.random())
        player.risk = min(100.0, player.risk + incr)
        return (
            "Falha. Os firewalls internos te estranham.\n"
            f"Risco aumentado em {incr:.1f}%."
        )

    hrs = random.randint(4, 8)
    player.hours_pass(hrs, world)


# -------------------- Loja --------------------
SHOP = {
    "raspberry": {"price": 150.0, "desc": "Hardware barato. +5 exploit"},
    "proxy_pack": {"price": 300.0, "desc": "Serviços de proxy. +5 stealth"},
    "ritaline": {"price": 120.0, "desc": "4 comprimidos. Aumenta foco, mas pode causar vício"},
    "crawler_pack": {"price": 500.0, "desc": "Toolkit profissional de webcrawling. +6 recon"},
    "botnet_worm": {"price": 1800.0, "desc": "Aumenta chance. +20 exploit temporário após 30 dias e baixa renda passiva", "asset": {"type": "botnet_worm", "income_per_day": 30.0}},
    "vpn_node": {"price": 1200.0, "desc": "Nó VPN. Reduz traces", "asset": {"type": "vpn", "income_per_day": 0.0}},
    "rack": {"price": 2000.0, "desc": "Rack em colo. Renda passiva", "asset": {"type": "rack", "income_per_day": 100.0}},
    "datacenter_unit": {"price": 15000.0, "desc": "Unidade de datacenter", "asset": {"type": "datacenter", "income_per_day": 400.0}},
    "honeypot_api": {"price": 2500.0, "desc": "API mensal que detecta honeypots automaticamente", "asset": {"type": "honeypot_api", "income_per_day": 0.0}},
}

INVENTORY_BUFFS = {
    "raspberry": {"exploit": 5},
    "proxy_pack": {"stealth": 5},
    "crawler_pack": {"recon": 6}
}

def recalc_inventory_bonuses(player):
    # zera buffs temporários
    base = {"recon":1.0,"exploit":1.0,"stealth":1.0}
    # soma bônus de cada item presente
    for item in player.inventory:
        if item in INVENTORY_BUFFS:
            for k,v in INVENTORY_BUFFS[item].items():
                base[k] += v
    # aplica
    player.skills.update(base)


def buy_item(player, item, world):
    if item not in SHOP:
        return False, "Item não encontrado na loja."
    is_asset = "asset" in SHOP[item]

    # Ritaline nunca ocupa slot de inventário
    if item != "ritaline":
        if not is_asset and len(player.inventory) >= getattr(player, "inventory_limit", 6):
            return False, f"Inventário cheio. Limite: {player.inventory_limit} itens."

    cost = SHOP[item]["price"]
    if player.money < cost:
        return False, "Dinheiro insuficiente."

    # se for asset, perguntar região antes de deduzir
    if is_asset:
        if item == "honeypot_api":
            player.inventory.append(item)
            return True, "honeypot_api instalado."

        print(f"Regiões disponíveis para instalação:")
        for rn, meta in world.regions.items():
            if meta.get("unlocked"):
                print(f" - {rn} (diff {meta.get('difficulty')}) | state:{meta.get('state')} crime:{meta.get('crime')} hx:{meta.get('hacktivists')}")
        reg = input("Instalar ativo em qual região? ").strip()
        if reg not in world.regions or not world.regions[reg]["unlocked"]:
            return False, "Região inválida ou bloqueada."

    # confirmar compra
    player.money -= cost

    if item == "ritaline":
        player.ritaline_pills += 4
        return True, "Você comprou ritaline (4 comprimidos)."

    if is_asset:
        a = SHOP[item]["asset"].copy()
        a["bought_at"] = player.time.isoformat()
        a["item_name"] = item
        a["region"] = reg
        player.assets.append(a)
    else:
        player.inventory.append(item)
        if item == "botnet_worm":
            a = {"type": "botnet_worm", "income_per_day": 0.0, "bought_at": player.time.isoformat(), "item_name": item, "region": player.region}
            player.assets.append(a)
            player.skills["exploit"] += 20

    recalc_inventory_bonuses(player)
    return True, f"Comprado {item} por ${cost:.2f}."


def cmd_buy(player, args, world):
    if not args:
        s = "Loja disponível:\n"
        for k, v in SHOP.items():
            s += f" {k} - ${v['price']:.2f} - {v['desc']}\n"
        return s
    item = args[0]
    ok, msg = buy_item(player, item, world)
    return msg


def cmd_ritaline(player, args, world):
    if not args:
        return "Uso: ritaline <quantidade>"
    try:
        q = int(args[0])
    except ValueError:
        return "Quantidade inválida."

    if q <= 0:
        return "Quantidade deve ser positiva."

    if player.ritaline_pills < q:
        return "Você não possui tantos comprimidos."

    player.ritaline_pills -= q

    # efeito positivo
    boost = q * 12.5
    player.focus = min(100.0, player.focus + boost)

    # chance de vício aumenta com uso
    addiction_gain = q * random.uniform(6.0, 16.0)
    player.ritaline_addiction = min(100.0, player.ritaline_addiction + addiction_gain)

    msg = f"Você tomou {q} comprimido(s). Foco +{boost:.1f}%."

    # verificar se tornou-se viciado
    if random.random() < (player.ritaline_addiction / 140):
        player.push_alert("Você desenvolveu dependência de ritaline. Foco passa a cair 2x mais rápido.")
        player.ritaline_addicted = True
        player.ritaline_addiction = 100.0  # inicia viciado
        msg += " Você agora está viciado."

    return msg


def cmd_status(player, args, world):
    jail = "Sim" if player.in_jail() else "Não"
    assets_str = ""
    if player.assets:
        for i, a in enumerate(player.assets, 1):
            name = a.get("item_name", a.get("type", "asset"))
            assets_str += f" {i}. {name}({a.get('type')})[{a.get('region','?')}] "
    else:
        assets_str = "Nenhum"
    hist_tail = list(player.command_history)[-5:]
    recent = "\n".join(hist_tail) if hist_tail else "Nenhum"
    inv_count = len(player.inventory)
    inv_limit = getattr(player, "inventory_limit", 6)
    return (
        f"Tempo: {player.time.strftime('%Y-%m-%d %H:%M')}\n"
        f"Região atual: {player.region}\n"
        f"Dinheiro: ${player.money:.2f}\n"
        f"Skills: {player.skills}\n"
        f"Foco: {player.focus:.1f}%\n"
        f"Risco: {player.risk:.1f}%\n"
        f"Inventário ({inv_count}/{inv_limit}): {player.inventory}\n"
        f"Ativos: {assets_str}\n"
        f"Ritaline: {player.ritaline_pills} comprimidos | Vício: {player.ritaline_addiction:.1f}%\n"
        f"Conhecimento: {player.knowledge}\n"
        f"Reputação: {player.reputation}\n"
        f"Dias no mundo: {world.day}\n"
        f"IA's inimigas: {len(world.enemy_ais)}\n"
        f"Comandos recentes:\n{recent}"
    )


def cmd_sleep(player, world):
    hrs = random.randint(8, 11)
    player.hours_pass(hrs, world)
    player.focus = min(100.0, player.focus + hrs * 1.8)
    player.risk = max(0.0, player.risk - hrs * 1.3)
    return f"Você descansou por {hrs} horas. Concentração restaurada e risco reduzido."


def cmd_job(player, world):
    if player.focus < MIN_FOCUS_JOB:
        return (
            "Você está mentalmente exausto para trabalhar.\n"
            "Forçar agora só chamaria atenção indesejada."
        )

    hrs = random.randint(4, 8)
    player.hours_pass(hrs, world)

    pay = random.randint(60, 120)
    player.money += pay

    player.focus = max(0.0, player.focus - hrs * 6)

    warning = ""
    if player.focus < 30:
        warning = " Você está exausto."

    bonus_rep = random.randint(1, 3)
    player.reputation["state"] += bonus_rep
    player.reputation["crime"] = max(0, player.reputation["crime"] - 1)

    # punição se zerar foco
#    if player.focus == 0:
#        apply_zero_focus_penalty(player, world)

    return (
        f"Trabalho concluído: +${pay}. "
        f"Concentração atual: {player.focus:.1f}%.{warning}\n"
        f"Reputação estatal +{bonus_rep}. Crime -1."
    )


def cmd_job_state(player, args, world):
    if player.reputation.get("state", 0) < 25:
        return "Você ainda não tem confiança suficiente do Estado."

    # Alvo temporário para auditoria
    class GovAudit:
        def __init__(self):
            self.security = 7 + int(player.reputation["state"] / 4)
            self.reward = 1000 + player.reputation["state"] * 400
            self.trace_speed = 0.7

    target = GovAudit()
    title = "Auditoria Interna — Setor Classificado"

    print("\n[STATE] Contrato autorizado pelo núcleo sigiloso.\n")
    visual_mission_roll(calc_hack_chance(player, target), player, title)

    roll = random.random()
    chance = calc_hack_chance(player, target)

    if roll < chance:
        player.money += target.reward
        player.skills["recon"] += 1.5
        player.skills["exploit"] += 1.5
        player.focus = min(100, player.focus + 4)

        # Estado gosta — crime continua feio
        player.reputation["state"] += 2
        player.reputation["crime"] += 1

        return (
            f"Sucesso! Estado pagou ${target.reward:.2f}.\n"
            "A vigilância agradece sua colaboração."
        )
    else:
        incr = target.security * (0.8 + random.random())
        player.risk = min(100.0, player.risk + incr)
        return (
            "Falha. Os firewalls internos te estranham.\n"
            f"Risco aumentado em {incr:.1f}%."
        )


def cmd_study(player, args, world):
    if player.focus < MIN_FOCUS_STUDY:
        return (
            "Foco insuficiente para estudar.\n"
            f"Necessário: {MIN_FOCUS_STUDY}%. Atual: {player.focus:.1f}%.\n"
            "Talvez dormir antes seja uma boa ideia."
        )

    hrs = 4
    if args:
        try:
            hrs = int(args[0])
        except ValueError:
            return "study: argumento inválido"

    return study(player, hrs, world)


def cmd_train(player, args):
    if len(args) < 2:
        return "train: uso train <skill> <pontos>"
    skill = args[0]
    try:
        pts = int(args[1])
    except ValueError:
        return "train: pontos inválidos"
    ok, msg = train(player, skill, pts)
    return msg


def cmd_assets(player, args):
    if not player.assets:
        return "Nenhum ativo."
    s = "Ativos:\n"
    for i, a in enumerate(player.assets, 1):
        s += f" {i}. {a['type']} - renda/dia: ${a.get('income_per_day', 0.0):.2f} - região: {a.get('region','?')}\n"
    return s


def cmd_map(player, args, world):
    print("""

                            P  5  P5!5555 55
                        55     5!555 5  P                              5
                              :P5  !P555555                   P          55
                           5      5 555  !                  5   5  55   !5   55
                  55  P P 5   5    5555PP          ?   5P   P5 55  5   55  P55555 5555
       P P    555   55?5 55  55    P 5            P55555555  5PPP  555    5555 P5 P 55555^ P
        ~5  P   5 P55575.   55.                  55  55  PPP5   .  5 :P5P PP   55555    55
         5    ?555    55 5  5   5                    57  ~P55 ~P55~5:5P55P75  P       5
                P P555P55555   7 5             5  5 755  PPPP^5P  P   555555P55 575
                  5P  555P:P555              5 P55.5?Y5   5 PP 55 55   5P!75 555P 5
                  Y5P55P555 5                 5       P5:55P   Y555.   5  55  5
                    5PP5   5                 5  55?5 PP   5   ~P75PP5P55  !55
                     5                      5P~55    557  5?55  5 5   P ! .5
                        P                  .5  555  P  55        5 55   55
                            5 55P           55555  P5555555        5
                           75 Y5  P5              55  5                 . 5     .
                              55P5PP5              P55555
                                 P 5              5  55    5                   555 5
                              555P55                  5P  5                55~   5 P5
                             5 5.                   55                      5    .P       5
                             55^                                                        5
                             5P
                              5

""")
    s = "Mapa de regiões (desbloqueio automático por tempo):\n"
    for name, meta in world.regions.items():
        s += (f" - {name}: {'Desbloqueado' if meta['unlocked'] else 'Bloqueado'} "
              f"(diff {meta['difficulty']}) | state:{meta.get('state',0)} crime:{meta.get('crime',0)} hx:{meta.get('hacktivists',0)}\n")
    return s


def ascii_travel_cutscene(mode, region):
    if mode == "normal":
        # Estilo "aeroporto"
        return (
            "\n\n"
            "  ████████████████████████████████████████\n"
            "  █        SISTEMA DE EMBARQUE AIRSING     █\n"
            "  ████████████████████████████████████████\n"
            "  ▓▓  CHECK-IN AUTOMÁTICO EM PROGRESSO  ▓▓\n"
            "  ░░────────────────────────────────────░░\n"
            f"      PORTÃO: D-{hash(region)%30:02d}   VOO: NX{abs(hash(region))%900+100}\n"
            f"      DESTINO: {region:<14} STATUS: LIBERADO\n"
            "  ░░────────────────────────────────────░░\n"
            "     Passageiro autenticado. Bagagem criptografada.\n"
            "            Favor aguardar o embarque...\n\n"
        )
    else:
        # Sub-rede clandestina permanece sombria e intensa
        return (
            "\n\n"
            "██████████████████████████████████████████\n"
            "█     ENTRANDO EM SUB-REDE FANTASMA      █\n"
            "██████████████████████████████████████████\n"
            "▓▓▓─┤┤ ROTA FORA DO RADAR ├┤─▓▓▓\n"
            "   Identidade → Quebra total\n"
            "   Spoofing → MÁXIMO\n"
            "   Proxy-chains → ENCADEADO\n"
            "░░░ Logs se dissolvendo em ruídos digitais...\n"
            "░░░ Você não existe para os satélites.\n\n"
            f"        Destino final: {region}\n"
            "        Cuidado com olhos sem corpo.\n\n"
        )


def cmd_travel(player, args, world):
    if not args:
        return "travel: uso travel <regiao> [normal|clandestino]"

    region = args[0]
    mode = args[1] if len(args) > 1 else "normal"
    if region not in world.regions:
        return "Região desconhecida."
    if not world.regions[region]["unlocked"]:
        return "Região ainda bloqueada."

    # região atual pode não existir ainda
    diff_atual = world.regions.get(getattr(player, "region", None), {}).get("difficulty", 1)
    diff_dest = world.regions[region]["difficulty"]

    base_cost = 500 * diff_dest
    base_time = 12 + 4 * diff_dest

    if mode == "normal":
        cost = base_cost
        hrs = base_time
        risk_drop = max(1.0, abs(diff_atual - diff_dest) * 2.8)
    elif mode == "clandestino":
        cost = int(base_cost * 6.5)
        hrs = int(base_time * 1.6)
        risk_drop = 42 + diff_dest * 4
    else:
        return "Modo inválido. Use 'normal' ou 'clandestino'."

    if player.money < cost:
        return "Dinheiro insuficiente para viajar."

    # aplicação dos efeitos
    player.money -= cost
    player.hours_pass(hrs, world)
    player.risk = max(0.0, player.risk - risk_drop)
    player.region = region

    # benefícios clandestinos
    if mode == "clandestino":
        # pequenas chances de ruído no mundo
        if random.random() < 0.25 and hasattr(world, "last_alerts"):
            player.reputation["crime"] += 1

        if hasattr(world, "enemy_ais"):
            world.enemy_ais.clear()
        if hasattr(world, "last_scan"):
            world.last_scan.clear()
        if hasattr(world, "last_alerts"):
            world.last_alerts.clear()

        # stealth sempre existe no Player dentro dessa estrutura
        player.skills["stealth"] = player.skills.get("stealth", 0) + 2

    scene = ascii_travel_cutscene(mode, region)

    return (
        scene +
        f"Viagem realizada para {region} via {mode}.\n"
        f"Custo: ${cost:.2f} | Tempo: {hrs}h | Risco reduzido em {risk_drop:.1f}%.\n"
        + ("Rastro totalmente zerado. IAs perderam sua localização.\n" if mode == "clandestino" else "")
    )


def cmd_history(player, args):
    return "\n".join(player.command_history) if player.command_history else "Sem histórico."


def cmd_spawn_ai(player, args, world):
    """Spawn manual para debug: spawn_ai [type] [region]"""
    preferred = args[0] if args else None
    region = args[1] if len(args) > 1 else player.region
    ai = world.spawn_enemy_ai(preferred_type=preferred, region=region, player=player)
    return f"IA inimiga {ai.uid} (tipo oculto) iniciada em {region} (debug spawn)."


def cmd_news(player, args, world):
    """news [region] — mostra notícias regionais desbloqueadas ou de uma região específica."""
    if not args:
        out = []
        for region, meta in world.regions.items():
            if meta.get("unlocked"):
                out.append(world.generate_news_for_region(region, player))
        return "\n\n".join(out)
    region = args[0]
    if region not in world.regions:
        return "Região desconhecida."
    if not world.regions[region]["unlocked"]:
        return "Região bloqueada."
    return world.generate_news_for_region(region, player)


# -------------------- Treino e estudo --------------------
def study(player, hrs, world):
    player.hours_pass(hrs, world)
    gain = max(1, int(hrs * (1 + (0.1 - (player.skills["recon"] + player.skills["exploit"]) / 2) * 0.2)))
    player.knowledge += gain
    player.focus = max(0.0, player.focus - hrs * 6)

    if player.focus < 30:
        warning = "Você está exausto. Sua concentração está muito baixa."
    else:
        warning = ""
    return f"Estudou por {hrs} horas e ganhou {gain} pontos de conhecimento.\nConcentração atual: {player.focus:.1f}%. {warning}"


def train(player, skill, points):
    if skill not in player.skills:
        return False, "Skill desconhecida."
    if points <= 0:
        return False, "Pontos inválidos."
    if player.knowledge < points:
        return False, "Conhecimento insuficiente."
    player.knowledge -= points
    improvement = points * 0.3
    player.skills[skill] += improvement
    player.skills[skill] = round(player.skills[skill], 2)
    return True, f"{skill} aumentada em {improvement:.2f}."


# -------------------- Utilitários --------------------
def join_path(cwd, target):
    import os
    if target.startswith("/"):
        return os.path.normpath(target)
    return os.path.normpath(os.path.join(cwd, target))


def ls(fs, path):
    if path in fs and fs[path]["type"] == "dir":
        return fs[path]["children"]
    elif path in fs and fs[path]["type"] == "file":
        return [path.split("/")[-1]]
    else:
        return None


def cat(fs, path):
    if path in fs and fs[path]["type"] == "file":
        return fs[path]["content"]
    return None


# -------------------- Loop principal --------------------
def repl():
    import time, sys, random

    clear_screen()
    time.sleep(0.2)
    sys.stdout.write("\a")
    sys.stdout.flush()

    # ===== SECURE BOOT SHOCK =====
    sys.stdout.write("\a")
    sys.stdout.flush()
    time.sleep(random.uniform(0.32, 3.35))

    # ===== BIOS ALERT - CLASSIFIED =====
    bios_options = [
        [
            "BlackIce Secure UEFI Loader v7.8",
            "Cryptographic Hardware Seal.............OK",
            "Anti-Forensic Module...................ARMED",
            "AI Surveillance Kernel.................ENABLED",
            "Traceback Prevention...................ACTIVE",
        ],
        [
            "Classified Firmware: Clearance Level RED",
            "Zero Trust Boot Chain..................INTACT",
            "Threat Monitoring (Global).............ONLINE",
            "Network Counter-Intrusion..............READY",
            "Identity Spoofing Allowed..............YES",
        ],
        [
            "Quantum Hardened Hypervisor ROM",
            "Virtual Host Fingerprint...............MASKED",
            "Anomaly Matrix..........................CLEAN",
            "Offensive Modules.......................LOADED",
            "Rootkit Shield.........................DISENGAGED",
        ],
        [
            "Stealth Firmware - DO NOT DISTRIBUTE",
            "Hardware Identity......................OBFUSCATED",
            "System Attestation.....................FAILED (?)",
            "This Device Is Not Officially Registered",
            "Proceeding Anyway...",
        ],
    ]

    bios_lines = random.choice(bios_options)

    # ===== Boot Progress Bar =====
    boot_frames = [
        "▏░░░░░░░░░░░░░░░░░▏",
        "▏▒░░░░░░░░░░░░░░░░▏",
        "▏▒▒░░░░░░░░░░░░░░░▏",
        "▏▓▒▒░░░░░░░░░░░░░░▏",
        "▏▓▓▒▒░░░░░░░░░░░░░▏",
        "▏▓▓▓▒▒░░░░░░░░░░░░▏",
        "▏▓▓▓▓▒▒░░░░░░░░░░░▏",
        "▏▓▓▓▓▓▒▒░░░░░░░░░░▏",
        "▏▓▓▓▓▓▓▒▒░░░░░░░░░▏",
        "▏▓▓▓▓▓▓▓▒▒░░░░░░░░▏",
        "▏▓▓▓▓▓▓▓▓▒▒░░░░░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▒▒░░░░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▒▒░░░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▒▒░░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▒▒░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▓▒░░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒░░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒░▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▏",
        "▏▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▏"
    ]

    sys.stdout.write("\nBooting unauthorized system...\n")

    for frame in boot_frames:
        sys.stdout.write(f"\r{frame}")
        sys.stdout.flush()
        time.sleep(random.uniform(0.03, 0.12))

        # Chance de glitch visual
        if random.random() < 0.06:
            sys.stdout.write("\r▏░░░FIRMWARE CORRUPTED░░░▏")
            sys.stdout.flush()
            time.sleep(random.uniform(0.03, 0.09))
            sys.stdout.write(f"\r{frame}")
            sys.stdout.flush()

    sys.stdout.write("\r[STEALTH MODE ENGAGED]\n\n")
    time.sleep(random.uniform(0.28, 0.65))

    # ===== BIOS Logs com falhas sutis =====
    for line in bios_lines:
        if random.random() < 0.07:
            # glitch sonoro
            sys.stdout.write("\a")
            sys.stdout.flush()
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
        time.sleep(random.uniform(0.25, 0.46))

        # chance de erro transitório
        if random.random() < 0.05:
            sys.stdout.write("Unexpected interrupt....handled\n")
            sys.stdout.flush()
            time.sleep(random.uniform(0.08, 0.20))

    # ===== OS Bring-Up =====
    boot_msgs = [
        "Deploying cyberwarfare subsystems...",
        "Encrypting volatile memory...",
        "Globally poisoning telemetry signals...",
        "Forging legal identity metadata...",
        "Monitoring federated agencies...",
        "Bypassing security enforcement...",
        "Injecting deepfake credentials...",
        "Preparing covert operations shell...",
        "System ready for infiltration.",
    ]

    print()

    ghost_frames = ["...", ". .", ".x.", ". .", "..."]

    for msg in boot_msgs:
        base = msg.rstrip(".")

        # animação Ghost Glitch
        for frame in ghost_frames:
            sys.stdout.write(f"\r{base}{frame}")
            sys.stdout.flush()
            time.sleep(random.uniform(0.32, 0.52))

        # fixa linha final
        sys.stdout.write("\r" + msg + "\n")
        sys.stdout.flush()

        # eventos extras
        if random.random() < 0.05:
            sys.stdout.write(">> Shadow redundancy engaged\n")
            sys.stdout.flush()
            time.sleep(random.uniform(1.10, 2.35))


    sys.stdout.write("\a")
    sys.stdout.flush()
    time.sleep(random.uniform(2.40, 3.70))

    print("\nAuthentication Required.\n")

    # ===== User Credentials =====
    username = ""
    while not username:
        username = input("alias: ").strip()
        if not username:
            print("Invalid codename.")

    global world
    player = Player()
    player.name = username
    world = World()

    print(f"\nConnection established, {player.name}.")
    time.sleep(random.uniform(0.3, 0.6))
    print("Type 'help' to initiate operations.")
    time.sleep(random.uniform(0.5, 0.8))


    # === Loop principal continua inalterado ===
    while True:
        # >>> GAME OVER IMEDIATO POR PRISÃO <<<
        if hasattr(player, "jailed") and player.jailed:
            print("\n...")
            time.sleep(1.0)
            print("\nVocê foi localizado pelo inimigo.\n")
            time.sleep(1.0)
            print("\n\tGAME OVER\n")
            time.sleep(1.0)
            sys.exit(0)

        if player.game_over:
            print("\n...")
            time.sleep(1.0)
            print("\n\tGAME OVER\n")
            time.sleep(1.0)
            sys.exit(0)

        # após cada comando, mostrar alertas mundiais recentes (se existirem)
        if hasattr(world, "last_alerts") and world.last_alerts:
            alerts = list(world.last_alerts)
            world.last_alerts.clear()
            for day, alert in alerts:
                player.push_alert(f"[Dia {day}] {alert}", delay=False)

        # === FEEDBACK DAS IAS (opção 2, corrigido) ===
        if hasattr(world, "enemy_ais"):
            for ai in world.enemy_ais:
                last_action = getattr(ai, "last_action", None)
                if last_action:
                    ai_type = getattr(ai, "type", None) or getattr(ai, "ai_type", None) or "Desconhecida"
                    prefix = {
                        "Pirata": "[IA Pirata]",
                        "Federal": "[IA Federal]",
                        "Hacktivista": "[IA Hacktivista]"
                    }.get(ai_type, "[IA Desconhecida]")
                    log_entry = f"{prefix} {last_action}"

                    if hasattr(world, "ai_activity_logs"):
                        world.ai_activity_logs.append(f"Day {world.day} - {log_entry}")

                    player.push_alert(f"[Dia {world.day}] {log_entry}")
                    ai.last_action = None

        try:
            prompt = f"{player.name}@simulation:{player.cwd}$ "
            try:
                line = input(prompt)
            except UnicodeDecodeError:
                # Recupera entrada mesmo se vier byte inválido
                raw = sys.stdin.buffer.readline()
                line = raw.decode("utf-8", errors="replace").rstrip("\n")

        except (KeyboardInterrupt, EOFError):
            print("\nSaindo...")
            break

        cmdline = line.strip()
        if not cmdline:
            continue
        player.record_command(cmdline)

        parts = cmdline.split()
        cmd = parts[0]
        args = parts[1:]

        # execute commands
        if cmd == "help":
            print(cmd_help())
        elif cmd == "ls":
            print(cmd_ls(player, args))
        elif cmd == "cd":
            print(cmd_cd(player, args))
        elif cmd == "cat":
            print(cmd_cat(player, args))
        elif cmd == "scan":
            out = cmd_scan(player, args, world)
            print(out)
            ev = trigger_random_event(player, world)
            if ev: print("\n" + ev)
            unlocks = check_reputation_unlocks(player, world)
            for u in unlocks: print(trigger_reputation_event(player, world, u))
        elif cmd == "connect":
            print(cmd_connect(player, args, world))
            ev = trigger_random_event(player, world)
            if ev: print("\n" + ev)
            unlocks = check_reputation_unlocks(player, world)
            for u in unlocks: print(trigger_reputation_event(player, world, u))
        elif cmd == "hack":
            print(cmd_hack(player, args, world))
            ev = trigger_random_event(player, world)
            if ev: print("\n" + ev)
            unlocks = check_reputation_unlocks(player, world)
            for u in unlocks: print(trigger_reputation_event(player, world, u))
        elif cmd == "buy":
            result = cmd_buy(player, args, world)
            print(result)
            ev = trigger_random_event(player, world)
            if ev: print("\n" + ev)
            unlocks = check_reputation_unlocks(player, world)
            for u in unlocks: print(trigger_reputation_event(player, world, u))
        elif cmd == "drop":
            if not args:
                print("drop: especificar item")
            else:
                item = args[0]
                if item in player.inventory:
                    player.inventory.remove(item)
                    recalc_inventory_bonuses(player)
                    print(f"Item {item} descartado.")
                else:
                    print("Item não encontrado no inventário.")
        elif cmd == "remove_asset":
            if not args:
                print("remove_asset: especificar índice do ativo")
            else:
                try:
                    idx = int(args[0]) - 1
                    if 0 <= idx < len(player.assets):
                        removed = player.assets.pop(idx)
                        print(f"Ativo {removed.get('item_name', removed.get('type'))} removido.")
                    else:
                        print("Índice inválido.")
                except ValueError:
                    print("Índice inválido.")
        elif cmd == "status":
            print(cmd_status(player, args, world))
        elif cmd == "ritaline":
            print(cmd_ritaline(player, args, world))
        elif cmd == "sleep":
            print(cmd_sleep(player, world))
            ev = trigger_random_event(player, world)
            if ev: print("\n" + ev)
            unlocks = check_reputation_unlocks(player, world)
            for u in unlocks: print(trigger_reputation_event(player, world, u))
        elif cmd == "study":
            print(cmd_study(player, args, world))
            ev = trigger_random_event(player, world)
            if ev: print("\n" + ev)
            unlocks = check_reputation_unlocks(player, world)
            for u in unlocks: print(trigger_reputation_event(player, world, u))
        elif cmd == "train":
            print(cmd_train(player, args))
            ev = trigger_random_event(player, world)
            if ev: print("\n" + ev)
            unlocks = check_reputation_unlocks(player, world)
            for u in unlocks: print(trigger_reputation_event(player, world, u))
        elif cmd == "jobs":
            print(cmd_job(player, world))
            ev = trigger_random_event(player, world)
            if ev: print("\n" + ev)
            unlocks = check_reputation_unlocks(player, world)
            for u in unlocks: print(trigger_reputation_event(player, world, u))
        elif cmd == "job_state":
            # --- Cooldown: verificar se já pode usar ---
            if player.next_job_state_time and player.time < player.next_job_state_time:
                delta = player.next_job_state_time - player.time
                dias = delta.days
                horas = delta.seconds // 3600
                print(f"job_state indisponível. Aguarde {dias} dia(s) e {horas} hora(s).")
            else:
                # executar normalmente
                print(cmd_job_state(player, args, world))
                # sortear intervalo entre 7 e 15 dias
                wait_days = random.randint(7, 15)
                player.next_job_state_time = player.time + timedelta(days=wait_days)
            # eventos normais pós-comando
            ev = trigger_random_event(player, world)
            if ev: print("\n" + ev)
            unlocks = check_reputation_unlocks(player, world)
            for u in unlocks: print(trigger_reputation_event(player, world, u))
        elif cmd == "mission":
            if not args:
                print("Usage: mission <id>")
            else:
                success, m = attempt_special_mission(player, world, args[0])
                print(m)
            ev = trigger_random_event(player, world)
            if ev: print("\n" + ev)
            unlocks = check_reputation_unlocks(player, world)
            for u in unlocks: print(trigger_reputation_event(player, world, u))
        elif cmd == "assets":
            print(cmd_assets(player, args))
        elif cmd == "map":
            print(cmd_map(player, args, world))
        elif cmd == "travel":
            print(cmd_travel(player, args, world))
            ev = trigger_random_event(player, world)
            if ev: print("\n" + ev)
            unlocks = check_reputation_unlocks(player, world)
            for u in unlocks: print(trigger_reputation_event(player, world, u))
        elif cmd == "history":
            print(cmd_history(player, args))
        elif cmd == "spawn_ai":
            print(cmd_spawn_ai(player, args, world))
        elif cmd == "news":
            print(cmd_news(player, args, world))
        elif cmd == "exit":
            print("Encerrado.")
            break
        else:
            print("Comando não reconhecido. Digite help.")
            player.maybe_game_over()

        # >>> Checagem FINAL de prisão após comando <<<
        if hasattr(player, "jailed") and player.jailed:
            print("...") # introduzir mais mansagens e randomizar
            time.sleep(1)
            print("\n\tGAME OVER\n")
            time.sleep(1)
            sys.exit(0)


if __name__ == "__main__":
    repl()
