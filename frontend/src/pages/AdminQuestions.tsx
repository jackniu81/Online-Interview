import { FormEvent, useCallback, useEffect, useState } from 'react'
import Markdown from '../components/Markdown'
import { api } from '../lib/api'
import type { Page, Question, QuestionListItem } from '../lib/types'

const PAGE_SIZE = 20

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: 8,
  boxSizing: 'border-box',
}

interface Editing {
  id: number | null // null = create
  content: string
  reference_answer: string
}

export default function AdminQuestions() {
  const [data, setData] = useState<Page<QuestionListItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: PAGE_SIZE,
  })
  const [keyword, setKeyword] = useState('')
  const [editing, setEditing] = useState<Editing | null>(null)
  const [preview, setPreview] = useState<Question | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(
    async (page = 1) => {
      const resp = await api.get('/admin/questions', {
        params: { page, page_size: PAGE_SIZE, q: keyword },
      })
      setData(resp.data)
    },
    [keyword],
  )

  useEffect(() => {
    load(1).catch(() => {})
  }, [load])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!editing) return
    setError('')
    const body = { content: editing.content, reference_answer: editing.reference_answer }
    try {
      if (editing.id === null) await api.post('/admin/questions', body)
      else await api.put(`/admin/questions/${editing.id}`, body)
      setEditing(null)
      await load(data.page)
    } catch (err: any) {
      setError(err.response?.status === 422 ? '题目内容与参考答案均不能为空' : '保存失败')
    }
  }

  async function remove(id: number) {
    if (!window.confirm('确认删除该题目？已被考试引用的题目不受影响。')) return
    await api.delete(`/admin/questions/${id}`)
    await load(data.page)
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input
          placeholder="搜索题目关键字"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ ...inputStyle, maxWidth: 300 }}
        />
        <button onClick={() => setEditing({ id: null, content: '', reference_answer: '' })}>
          新建题目
        </button>
      </div>

      <table border={1} cellSpacing={0} cellPadding={8} style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ width: 60 }}>ID</th>
            <th>题目摘要</th>
            <th style={{ width: 170 }}>创建时间</th>
            <th style={{ width: 200 }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((item) => (
            <tr key={item.id}>
              <td>{item.id}</td>
              <td>{item.summary}</td>
              <td>{new Date(item.created_at).toLocaleString()}</td>
              <td>
                <button onClick={() => setPreview(item)}>预览</button>{' '}
                <button
                  onClick={() =>
                    setEditing({ id: item.id, content: item.content, reference_answer: item.reference_answer })
                  }
                >
                  编辑
                </button>{' '}
                <button onClick={() => remove(item.id)}>删除</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 8, color: '#666' }}>
        共 {data.total} 题 · 第 {data.page} 页{' '}
        <button disabled={data.page <= 1} onClick={() => load(data.page - 1)}>
          上一页
        </button>{' '}
        <button disabled={data.page * PAGE_SIZE >= data.total} onClick={() => load(data.page + 1)}>
          下一页
        </button>
      </div>

      {editing && (
        <Modal title={editing.id === null ? '新建题目' : `编辑题目 #${editing.id}`} onClose={() => setEditing(null)}>
          <form onSubmit={onSubmit}>
            <label>题目内容（支持 Markdown/代码块）</label>
            <textarea
              rows={8}
              value={editing.content}
              onChange={(e) => setEditing({ ...editing, content: e.target.value })}
              style={inputStyle}
            />
            <label style={{ marginTop: 8, display: 'block' }}>参考答案</label>
            <textarea
              rows={6}
              value={editing.reference_answer}
              onChange={(e) => setEditing({ ...editing, reference_answer: e.target.value })}
              style={inputStyle}
            />
            {error && <p style={{ color: 'crimson' }}>{error}</p>}
            <div style={{ marginTop: 12, textAlign: 'right' }}>
              <button type="button" onClick={() => setEditing(null)} style={{ marginRight: 8 }}>
                取消
              </button>
              <button type="submit">保存</button>
            </div>
          </form>
        </Modal>
      )}

      {preview && (
        <Modal title={`题目预览 #${preview.id}`} onClose={() => setPreview(null)}>
          <div style={{ border: '1px solid #eee', padding: 12, maxHeight: 400, overflow: 'auto' }}>
            <Markdown content={preview.content} />
            <hr />
            <h4>参考答案</h4>
            <Markdown content={preview.reference_answer} />
          </div>
        </Modal>
      )}
    </div>
  )
}

function Modal({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: React.ReactNode
}) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.35)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        style={{ background: '#fff', padding: 20, borderRadius: 8, width: 640, maxWidth: '90vw' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        {children}
      </div>
    </div>
  )
}
