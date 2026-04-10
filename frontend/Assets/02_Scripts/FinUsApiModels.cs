using System;

[Serializable]
public class AnalyzeApiResponse
{
    public string status;
    public AnalyzeData data;
}

[Serializable]
public class AnalyzeData
{
    public string summary;
    public TradingDetails details;
    public string[] source_news;
    public string trading_trend;
}

[Serializable]
public class TradingDetails
{
    public string decision;
    public float confidence_score;
    public string reason;
    public string target_stock;
}

[Serializable]
public class NewsApiResponse
{
    public string status;
    public NewsData data;
}

[Serializable]
public class NewsData
{
    public string[] news;
}

[Serializable]
public class TrendApiResponse
{
    public string status;
    public TrendData data;
}

[Serializable]
public class TrendData
{
    public string trend;
}

public class TrendItem
{
    public string date;
    public int price;
    public string changeVal;
    public string changePct;
    public bool isUp;
    public int foreigner;
    public int institution;
    public int volume;
}

public class DataOnlyResult
{
    public string[] newsItems;
    public string trendRaw;
}

[Serializable]
public class ErrorDetailResponse
{
    public string detail;
}
