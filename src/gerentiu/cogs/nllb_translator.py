from __future__ import annotations

from pathlib import Path
import ctranslate2
from transformers import AutoTokenizer

LANG_MAP = {
    "pt": "por_Latn",
    "en": "eng_Latn",
    "es": "spa_Latn",
    "fr": "fra_Latn",
    "de": "deu_Latn",
    "it": "ita_Latn",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
    "ru": "rus_Cyrl",
    "zh": "zho_Hans",
}

class NLLBTranslator:
    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        self.translator = ctranslate2.Translator(
            model_dir,
            device="cpu",
            inter_threads=2,
            intra_threads=6,
        )
        self.tokenizers = {}

    def _get_tokenizer(self, src_lang_code: str):
        if src_lang_code not in self.tokenizers:
            self.tokenizers[src_lang_code] = AutoTokenizer.from_pretrained(
                "facebook/nllb-200-distilled-600M",
                src_lang=src_lang_code,
            )
        return self.tokenizers[src_lang_code]

    def translate(self, text: str, src_lang: str, dst_lang: str) -> str:
        if not text.strip():
            return text

        src_code = LANG_MAP.get(src_lang)
        dst_code = LANG_MAP.get(dst_lang)

        if not src_code or not dst_code:
            raise ValueError(f"Language not supported for NLLB: {src_lang=} {dst_lang=}")

        tokenizer = self._get_tokenizer(src_code)

        source_tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(text))
        results = self.translator.translate_batch(
            [source_tokens],
            target_prefix=[[dst_code]],
            beam_size=4,
            max_decoding_length=256,
        )

        target_tokens = results[0].hypotheses[0][1:]
        translated = tokenizer.decode(
            tokenizer.convert_tokens_to_ids(target_tokens),
            skip_special_tokens=True,
        )
        return translated.strip()
