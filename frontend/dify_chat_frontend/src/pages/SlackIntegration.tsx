import { useState, useEffect } from 'react'

interface InstallUrlResponse {
  install_url: string
}

export default function SlackIntegration() {
  const [installUrl, setInstallUrl] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchInstallUrl()
  }, [])

  const fetchInstallUrl = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/slack/install`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data: InstallUrlResponse = await response.json()
      setInstallUrl(data.install_url)
    } catch (error) {
      setError('インストールURLの取得に失敗しました。')
      console.error('Error fetching install URL:', error)
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">読み込み中...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-red-600">{error}</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 mb-8">
            Slackワークスペースに追加
          </h1>
          
          <div className="bg-white rounded-lg shadow-lg p-8">
            <p className="text-gray-600 mb-8">
              DifyAIエージェントをSlackワークスペースに追加して、チームメンバーと会話を始めましょう。
            </p>
            
            <div className="space-y-6">
              <div className="border-t border-gray-200 pt-6">
                <h2 className="text-lg font-medium text-gray-900 mb-4">
                  インストール手順
                </h2>
                <ol className="list-decimal list-inside space-y-4 text-gray-600">
                  <li>下の「Slackに追加」ボタンをクリックします</li>
                  <li>Slackの認証画面で、ワークスペースを選択します</li>
                  <li>必要な権限を確認し、「許可する」をクリックします</li>
                  <li>インストール完了後、Slackでボットとの会話を開始できます</li>
                </ol>
              </div>
              
              <div className="border-t border-gray-200 pt-6">
                <a
                  href={installUrl}
                  className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-gray-700 hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
                >
                  <img
                    src="https://platform.slack-edge.com/img/add_to_slack.png"
                    alt="Add to Slack"
                    className="h-5 mr-2"
                  />
                  Slackに追加
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
