const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const mongoose = require('mongoose');
const http = require('http');

// 初始化Express应用
const app = express();
const PORT = process.env.PORT || 3002;

// 中间件 - 增加请求体大小限制到50MB
app.use(cors());
app.use(bodyParser.json({ limit: '50mb' }));
app.use(bodyParser.urlencoded({ extended: true, limit: '50mb' }));

// 静态文件服务
app.use(express.static(__dirname));

// 数据库连接（使用MongoDB）
mongoose.connect('mongodb://localhost:27017/nlp-tool', {
  useNewUrlParser: true,
  useUnifiedTopology: true
}).then(() => {
  console.log('数据库连接成功');
}).catch((error) => {
  console.error('数据库连接失败:', error);
});

// 定义用户模型
const User = mongoose.model('User', {
  username: String,
  email: String,
  password: String,
  createdAt: Date
});

// 定义API配置模型
const ApiConfig = mongoose.model('ApiConfig', {
  userId: String,
  modelType: String,
  apiKey: String,
  apiUrl: String,
  updatedAt: Date
});

// 代理请求函数 - 使用127.0.0.1而不是localhost避免IPv6问题
function proxyRequest(targetUrl, req, res) {
  const urlObj = new URL(targetUrl);
  const options = {
    hostname: urlObj.hostname,
    port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
    path: urlObj.pathname + urlObj.search,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  };

  const proxyReq = http.request(options, (proxyRes) => {
    let data = '';
    proxyRes.on('data', (chunk) => data += chunk);
    proxyRes.on('end', () => {
      try {
        const jsonData = JSON.parse(data);
        res.status(proxyRes.statusCode).json(jsonData);
      } catch (e) {
        res.status(proxyRes.statusCode).send(data);
      }
    });
  });

  proxyReq.on('error', (error) => {
    res.status(500).json({ success: false, message: '代理请求失败: ' + error.message });
  });

  proxyReq.write(JSON.stringify(req.body));
  proxyReq.end();
}

// API路由

// 注册用户
app.post('/api/register', async (req, res) => {
  try {
    const { username, email, password } = req.body;

    // 检查用户是否已存在
    const existingUser = await User.findOne({ username });
    if (existingUser) {
      return res.status(400).json({ error: '用户名已存在' });
    }

    // 创建新用户
    const newUser = new User({
      username,
      email,
      password,
      createdAt: new Date()
    });

    await newUser.save();
    res.status(201).json({ message: '注册成功' });
  } catch (error) {
    res.status(500).json({ error: '注册失败' });
  }
});

// 登录用户
app.post('/api/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    // 查找用户
    const user = await User.findOne({ username, password });
    if (!user) {
      return res.status(401).json({ error: '用户名或密码错误' });
    }

    res.status(200).json({ message: '登录成功', user });
  } catch (error) {
    res.status(500).json({ error: '登录失败' });
  }
});

// 保存API配置
app.post('/api/api-config', async (req, res) => {
  try {
    const { userId, modelType, apiKey, apiUrl } = req.body;

    // 查找或创建API配置
    let config = await ApiConfig.findOne({ userId });
    if (!config) {
      config = new ApiConfig({
        userId,
        modelType,
        apiKey,
        apiUrl,
        updatedAt: new Date()
      });
    } else {
      config.modelType = modelType;
      config.apiKey = apiKey;
      config.apiUrl = apiUrl;
      config.updatedAt = new Date();
    }

    await config.save();
    res.status(200).json({ message: 'API配置保存成功' });
  } catch (error) {
    res.status(500).json({ error: '保存失败' });
  }
});

// 获取API配置
app.get('/api/api-config/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    const config = await ApiConfig.findOne({ userId });
    res.status(200).json(config || {});
  } catch (error) {
    res.status(500).json({ error: '获取失败' });
  }
});

// 健康检查
app.get('/api/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});

// 论文总结API代理
app.post('/api/proxy/summary', (req, res) => {
  proxyRequest('http://127.0.0.1:5001/api/summary', req, res);
});

// 论文检索API代理
app.post('/api/proxy/retrieve', (req, res) => {
  proxyRequest('http://127.0.0.1:5002/api/retrieve', req, res);
});

// 论文翻译API代理
app.post('/api/proxy/translate', (req, res) => {
  proxyRequest('http://127.0.0.1:5003/api/translate', req, res);
});

// 启动服务器
app.listen(PORT, () => {
  console.log(`服务器运行在 http://localhost:${PORT}`);
  console.log('\n========================================');
  console.log('AI文献辅助系统启动说明:');
  console.log('========================================');
  console.log('1. 主服务器（前端应用）: http://localhost:3002');
  console.log('2. 论文总结API服务: http://localhost:5001 (需要单独启动)');
  console.log('3. 论文检索API服务: http://localhost:5002 (需要单独启动)');
  console.log('4. 论文翻译API服务: http://localhost:5003 (需要单独启动)');
  console.log('5. 综述生成API服务: http://localhost:8002 (需要单独启动)');
  console.log('========================================\n');
});