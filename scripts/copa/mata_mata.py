"""
mata_mata.py
============
ConstrutorMataMata — monta os jogos das fases eliminatórias (mata-mata) a partir
da agenda oficial obtida da API e dos resultados reais.

Para cada confronto já definido (ambas as seleções conhecidas), calcula:
  • as probabilidades 3-vias do modelo — vitória / empate em 90' / derrota;
  • a probabilidade de avanço de cada lado = vitória no tempo normal + metade
    dos empates (a disputa de pênaltis é tratada como uma moeda 50/50, igual ao
    Monte Carlo).

As probabilidades pré-jogo são congeladas em knockout_probs.json na primeira vez
que o confronto é visto definido (antes da bola rolar), garantindo que não mudem
depois que a partida acontece nem sofram vazamento do próprio resultado.
"""

import datetime

from copa.ensemble import ModeloEnsemble
from copa.features import ExtratordeFeaturas
from copa.limiar_empate import PrevisorResultado
from copa.repositorio import RepositorioDados


class ConstrutorMataMata:
    """Constrói a lista de jogos do mata-mata com probabilidades do modelo."""

    # stage da football-data.org → (código interno, rótulo PT-BR, ordem da fase)
    FASES = {
        "LAST_32":        ("r32",   "16-avos de final",    1),
        "LAST_16":        ("r16",   "Oitavas de final",    2),
        "QUARTER_FINALS": ("qf",    "Quartas de final",    3),
        "SEMI_FINALS":    ("sf",    "Semifinal",           4),
        "THIRD_PLACE":    ("3rd",   "Disputa de 3º lugar", 5),
        "FINAL":          ("final", "Final",               6),
    }
    NAO_MATA_MATA = {"GROUP_STAGE", "LEAGUE_STAGE", "PRELIMINARY_ROUND", ""}

    def __init__(
        self,
        repositorio: RepositorioDados,
        ensemble: ModeloEnsemble,
        extrator: ExtratordeFeaturas,
        previsor: PrevisorResultado,
    ) -> None:
        """Recebe o repositório de dados, o ensemble, o extrator e o previsor."""
        self.repo     = repositorio
        self.ensemble = ensemble
        self.extrator = extrator
        self.previsor = previsor

    def _fase(self, stage: str):
        """Retorna (código, rótulo, ordem) da fase; None se não for mata-mata."""
        if stage in self.FASES:
            return self.FASES[stage]
        if stage in self.NAO_MATA_MATA:
            return None
        # Fallback genérico para nomes de fase não mapeados (robustez à API)
        return (stage.lower(), stage.replace("_", " ").title(), 9)

    @staticmethod
    def _brt(utc_str: str) -> str:
        """Converte um instante UTC (ISO) na data local de Brasília (UTC-3)."""
        dt  = datetime.datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        brt = dt - datetime.timedelta(hours=3)
        return brt.strftime("%Y-%m-%d")

    def _mapa_resultados(self) -> dict:
        """Mapeia (casa, fora) → resultado real, com avançante e pênaltis."""
        reais = self.repo.ler_json("resultados_reais.json", [])
        mapa: dict = {}
        for r in reais:
            h, a    = r["home_team"], r["away_team"]
            hs, as_ = int(r["home_score"]), int(r["away_score"])
            res     = "home" if hs > as_ else ("draw" if hs == as_ else "away")
            # Avançante: usa o campo explícito (pode ter sido nos pênaltis);
            # se ausente, deduz do placar do tempo normal.
            win = r.get("winner")
            if win not in ("home", "away"):
                win = "home" if hs > as_ else ("away" if as_ > hs else None)
            placar = f"{hs}-{as_}"
            if r.get("penalties"):
                placar += f" ({r['penalties']} pên)"
            mapa[(h, a)] = {"res": res, "placar": placar, "winner": win}
        return mapa

    def construir(self, flags: dict) -> list[dict]:
        """Monta a lista de confrontos de mata-mata definidos na agenda."""
        if not self.repo.existe("agenda.json"):
            return []

        agenda     = self.repo.ler_json("agenda.json", [])
        result_map = self._mapa_resultados()
        snapshot   = self.repo.ler_json("knockout_probs.json", {})
        mudou      = False

        jogos: list[dict] = []
        idc = 1001
        for m in agenda:
            fase = self._fase(m.get("stage", ""))
            if fase is None:
                continue
            h, a = m.get("home_team"), m.get("away_team")
            if not h or not a:
                continue  # confronto ainda sem as duas seleções definidas

            codigo, rotulo, ordem = fase
            fkey = f"{h}|{a}"

            if fkey in snapshot:
                s  = snapshot[fkey]
                ph, pd_, pa, pp = s["ph"], s["pd"], s["pa"], s["placar_prev"]
            else:
                fv = self.extrator.construir_vetor(h, a, m["utc"][:10], neutral=1)
                fph, fpd, fpa = self.ensemble.prever(h, a, fv)
                ph, pd_, pa = round(fph * 100, 2), round(fpd * 100, 2), round(fpa * 100, 2)
                pp = self.previsor.placar_previsto(fph, fpd, fpa)
                snapshot[fkey] = {"ph": ph, "pd": pd_, "pa": pa, "placar_prev": pp}
                mudou = True

            # Avanço = vitória em 90' + metade dos empates (pênaltis 50/50)
            adv_h = round(ph + pd_ / 2, 2)
            adv_a = round(pa + pd_ / 2, 2)

            real = result_map.get((h, a), {})
            jogos.append({
                "id":          idc,
                "g":           None,
                "s":           codigo,
                "fase":        rotulo,
                "ordem":       ordem,
                "date":        self._brt(m["utc"]),
                "venue":       m.get("venue", ""),
                "home":        h,
                "hf":          flags.get(h, "🏳️"),
                "away":        a,
                "af":          flags.get(a, "🏳️"),
                "ph":          ph,
                "pd":          pd_,
                "pa":          pa,
                "advH":        adv_h,
                "advA":        adv_a,
                "res":         real.get("res"),
                "placar":      real.get("placar"),
                "winner":      real.get("winner"),
                "placar_prev": pp,
                "time":        "",
                "utc":         m["utc"],
            })
            idc += 1

        if mudou:
            self.repo.salvar_json("knockout_probs.json", snapshot)

        jogos.sort(key=lambda j: (j["ordem"], j["utc"] or ""))
        return jogos
