# -*- coding: utf-8 -*-
"""stock-quality-screen：企业质量初筛。

版本号只有 config.VERSION 一处，这里直接引用——0.9.7 之前这里写着 0.1.0，
`screen.__version__` 与报告页脚的版本号对不上，排查问题时容易认错版本。
"""
from config import VERSION as __version__

__all__ = ["__version__"]
