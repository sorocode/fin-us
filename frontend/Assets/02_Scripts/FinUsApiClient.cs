using System;
using System.Collections;
using UnityEngine.Networking;

public class FinUsApiClient
{
    private readonly string apiBaseUrl;

    public FinUsApiClient(string apiBaseUrl)
    {
        this.apiBaseUrl = apiBaseUrl;
    }

    public IEnumerator FetchDataOnly(string stock, Action<DataOnlyResult> onSuccess, Action<string> onError)
    {
        var newsUrl = $"{apiBaseUrl}/api/v1/news?stock={UnityWebRequest.EscapeURL(stock)}";
        var trendUrl = $"{apiBaseUrl}/api/v1/trading/trend?stock={UnityWebRequest.EscapeURL(stock)}";

        using var newsReq = UnityWebRequest.Get(newsUrl);
        using var trendReq = UnityWebRequest.Get(trendUrl);

        yield return newsReq.SendWebRequest();
        if (newsReq.result != UnityWebRequest.Result.Success)
        {
            onError?.Invoke(ExtractErrorMessage(newsReq, "뉴스 조회 실패"));
            yield break;
        }

        yield return trendReq.SendWebRequest();
        if (trendReq.result != UnityWebRequest.Result.Success)
        {
            onError?.Invoke(ExtractErrorMessage(trendReq, "트렌드 조회 실패"));
            yield break;
        }

        var newsResponse = UnityEngine.JsonUtility.FromJson<NewsApiResponse>(newsReq.downloadHandler.text);
        var trendResponse = UnityEngine.JsonUtility.FromJson<TrendApiResponse>(trendReq.downloadHandler.text);

        onSuccess?.Invoke(new DataOnlyResult
        {
            newsItems = newsResponse?.data?.news ?? new string[0],
            trendRaw = trendResponse?.data?.trend ?? string.Empty
        });
    }

    public IEnumerator FetchAnalysis(string stock, string provider, Action<AnalyzeData> onSuccess, Action<string> onError)
    {
        var analyzeUrl = $"{apiBaseUrl}/api/v1/analyze?stock={UnityWebRequest.EscapeURL(stock)}&provider={UnityWebRequest.EscapeURL(provider)}";
        using var req = UnityWebRequest.Get(analyzeUrl);
        yield return req.SendWebRequest();

        if (req.result != UnityWebRequest.Result.Success)
        {
            onError?.Invoke(ExtractErrorMessage(req, "분석 실패"));
            yield break;
        }

        var parsed = UnityEngine.JsonUtility.FromJson<AnalyzeApiResponse>(req.downloadHandler.text);
        if (parsed == null || parsed.status != "success" || parsed.data == null)
        {
            onError?.Invoke("분석 데이터를 파싱하지 못했습니다.");
            yield break;
        }

        onSuccess?.Invoke(parsed.data);
    }

    private static string ExtractErrorMessage(UnityWebRequest request, string fallbackPrefix)
    {
        var body = request.downloadHandler?.text;
        if (!string.IsNullOrWhiteSpace(body))
        {
            var detail = UnityEngine.JsonUtility.FromJson<ErrorDetailResponse>(body);
            if (!string.IsNullOrWhiteSpace(detail?.detail))
            {
                return detail.detail;
            }
        }

        return $"{fallbackPrefix}: {request.error}";
    }
}
