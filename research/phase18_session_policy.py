"""Offline extension for authoritative date-specific special sessions."""
from datetime import date, time
from enum import Enum
from utils.session_policy import FiveMinuteSessionPolicy

class SpecialSessionRegime(str, Enum):
    SPECIAL_MUHURAT = 'SPECIAL_MUHURAT'

SPECIAL_SESSIONS = {
    date(2025,10,21): {
        'classification':'SPECIAL_MUHURAT',
        'regular_open':time(13,45),
        'regular_close':time(14,45),
        'final_bar_start':time(14,40),
        'entry_cutoff':time(14,45),
        'source':{'ref':'NSE/CMTR/70319','date':'2025-09-22','circular':'124/2025'},
    }
}

class Phase18SessionPolicy(FiveMinuteSessionPolicy):
    """Existing policy with an explicit, closed special-session registry."""
    def special_session(self, trading_date):
        return SPECIAL_SESSIONS.get(trading_date if isinstance(trading_date,date) else date.fromisoformat(str(trading_date)))
    def regime_for(self, trading_date):
        if self.special_session(trading_date) is not None:
            return SpecialSessionRegime.SPECIAL_MUHURAT
        return super().regime_for(trading_date)
    def final_regular_bar_start(self, trading_date):
        special=self.special_session(trading_date)
        return special['final_bar_start'] if special else super().final_regular_bar_start(trading_date)
    def entry_cutoff(self, trading_date):
        special=self.special_session(trading_date)
        return special['entry_cutoff'] if special else super().entry_cutoff(trading_date)
    def expected_bar_times(self, trading_date):
        special=self.special_session(trading_date)
        if special:
            from utils.time_utils import expected_bar_times
            return expected_bar_times(special['regular_open'],special['final_bar_start'],self.interval_minutes)
        return super().expected_bar_times(trading_date)
    def auxiliary_bar_times(self, trading_date):
        if self.special_session(trading_date): return ()
        return super().auxiliary_bar_times(trading_date)
    def metadata(self):
        value=super().metadata()
        value['special_sessions']={str(k):{'classification':v['classification'],'regular_open':v['regular_open'].isoformat(),'regular_close':v['regular_close'].isoformat(),'final_bar_start':v['final_bar_start'].isoformat(),'entry_cutoff':v['entry_cutoff'].isoformat(),'source':v['source']} for k,v in SPECIAL_SESSIONS.items()}
        return value
