"""Smoke-test the new source in the actual Streamlit application."""
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from real_data_catalog import available_sources


def check():
    root = Path(__file__).resolve().parents[2]
    app = AppTest.from_file(str(root/'main.py'), default_timeout=60).run()
    assert not app.exception
    app.radio(key='veri_modu_radio').set_value('📂 Veri Seti Yükle').run()
    name = next(name for name in available_sources() if name.startswith('CMU'))
    assert len(available_sources()) == 6
    app.selectbox(key='real_dataset_selection').set_value(name).run()
    app.button(key='load_real_dataset').click().run()
    assert not app.exception
    assert not app.error, [x.value for x in app.error]
    state = app.session_state
    assert state['dataset_summary']['adapter'] == 'cmu-flight-v1'
    assert len(state['dataset_df']) == 1339
    assert not state['cn0_available'] and not state['ground_truth_available']
    assert state['ml_source'] == 'unavailable'
    assert state['forensic_chain_valid']
    warnings = [x.value for x in app.warning]
    assert any('bağımsız nominal uçuş testi başarısız' in message for message in warnings)
    result = dict(source=name, available_sources=6, rows=len(state['dataset_df']),
                  ml_source=state['ml_source'], cn0_available=False,
                  labels_available=False, runtime_exceptions=0, errors=[],
                  independent_test_failure_warning_present=True,
                  forensic_chain_valid=True)
    (Path(__file__).parent/'ui_results.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    check()
