"""全局配置。所有 dev/prod 差异都收敛到环境变量，代码层零改动。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Riot API
    riot_api_key: str = "RGAPI-REPLACE-ME"
    # 默认只选样本量大、高分段环境稳定的三个服务器。
    regions: str = "kr,euw1,na1"   # 逗号分隔

    # 速率限制（dev/prod 唯一区别）
    rate_per_second: int = 20
    rate_per_two_min: int = 100
    max_matches_per_player: int = 20
    fetch_batch_size: int = 200

    # 服务器建议使用 PostgreSQL；默认 SQLite 只用于本地开发/测试快速启动。
    database_url: str = "sqlite:///tft_analysis.db"

    # 种子玩家最低段位。
    min_tier: str = "GRANDMASTER"

    # 只保留排位对局。TFT 排位队列 id = 1100（普通 1090、超级冲刺/双人等为其它值）
    ranked_queue_id: int = 1100

    @property
    def region_list(self) -> list[str]:
        return [r.strip() for r in self.regions.split(",") if r.strip()]


settings = Settings()
