"""
Unit tests for FFmpeg DSP Filtergraph Generation.
"""
from app.services.media.dsp import DSPFilterBuilder
from app.models.schemas import DSPConfig


def test_default_dsp_filter():
    filter_str = DSPFilterBuilder.build_audio_filtergraph(None)
    assert "aresample=48000" in filter_str
    assert "pan=stereo" in filter_str


def test_bass_boost_and_8d_filter():
    dsp = DSPConfig(bass_boost_db=6.0, spatial_8d=True, volume=120)
    filter_str = DSPFilterBuilder.build_audio_filtergraph(dsp)

    assert "volume=1.20" in filter_str
    assert "bass=g=6.0:f=110:w=0.6" in filter_str
    assert "apulsator=hz=0.125" in filter_str
    assert "aresample=48000" in filter_str


def test_nightcore_mode_filter():
    dsp = DSPConfig(nightcore=True)
    filter_str = DSPFilterBuilder.build_audio_filtergraph(dsp)

    assert "atempo=1.25" in filter_str
    assert "asetrate=48000*1.25" in filter_str


def test_video_filtergraph_scaling():
    vf_str = DSPFilterBuilder.build_video_filtergraph(width=1280, height=720, fps=30)
    assert "scale=1280:720" in vf_str
    assert "fps=30" in vf_str
