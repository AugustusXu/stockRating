import pandas as pd

def summary(single: dict) -> pd.DataFrame:
    summary_data = {k: v for k, v in single.items() if not isinstance(v, dict) and k != 'warnings'}
    df_summary = pd.DataFrame([summary_data])
    return df_summary

def indicators(single: dict) -> pd.DataFrame:

    rows = []
    categories = ['option_indicators', 'spot_indicators', 'gamma_indicators']

    for category in categories:
        # 遍历每个分类下的所有指标
        for ind_key, ind_val in single.get(category, {}).items():
            row = {
                'ticker': single['ticker'],
                'as_of': single['as_of'],
                'category': category,           # 记录所属的分类
                'name': ind_val.get('name'),
                'raw_value': ind_val.get('raw_value'),
                'score': ind_val.get('score'),
                'signal': ind_val.get('signal'),
                'explain': ind_val.get('explain'),
                'available': ind_val.get('available')
            }
            rows.append(row)
    return pd.DataFrame(rows)
