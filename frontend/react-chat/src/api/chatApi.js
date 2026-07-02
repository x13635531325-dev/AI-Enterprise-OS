export function mockSendMessage(userText) {
  return new Promise((resolve, reject) => {
    setTimeout(function () {
      const shouldFail = Math.random() < 0.3

      if (shouldFail) {
        reject(new Error('模拟 AI 接口请求失败'))
        return
      }

      resolve(`收到你的问题：“${userText}”。这是一个模拟的 AI 回复。后续会接入真实大模型 API。`)
    }, 1000)
  })
}