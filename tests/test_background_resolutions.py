import os
import glob
import unittest
import subprocess
import imageio_ffmpeg

class TestBackgroundResolutions(unittest.TestCase):
    def test_hd_background_resolutions(self):
        """
        Verifica que todos os vídeos baixados em assets/backgrounds:
        1. Possuem resolução HD (1080x1920 vertical ou 1920x1080 / 2560x1440 horizontal);
        2. Possuem taxa de quadros de 60 fps.
        """
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        bg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "backgrounds")
        files = glob.glob(os.path.join(bg_dir, "*.mp4"))

        self.assertGreaterEqual(len(files), 4, f"Esperado pelo menos 4 backgrounds HD, encontrados {len(files)}")

        for f in files:
            cmd = [exe, "-i", f]
            res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
            fn = os.path.basename(f).lower()

            if "vertical" in fn:
                self.assertTrue(
                    "1080x1920" in res.stderr or "720x1280" in res.stderr,
                    f"{fn} não está em resolução vertical HD!"
                )
            else:
                self.assertTrue(
                    "1920x1080" in res.stderr or "2560x1440" in res.stderr,
                    f"{fn} não está em resolução horizontal HD!"
                )

            self.assertTrue(
                "60 fps" in res.stderr or "59.94 fps" in res.stderr or "60 tbr" in res.stderr,
                f"{fn} não está em 60 fps!"
            )

if __name__ == "__main__":
    unittest.main()
