import { test, expect } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

test.describe('RAG Document Intelligence End-to-End Smoke Test', () => {
  test('Complete flow: demo login, upload PDF, poll job, ask question, citation, inspector', async ({ page }) => {
    // 1. Visit landing page
    await page.goto('/')
    await expect(page).toHaveTitle(/RAG Document Intelligence/i)

    // 2. Click "Try Live Demo" to perform 1-click recruiter authentication
    const demoButton = page.locator('button:has-text("Try Live Demo"), a:has-text("Try Live Demo")').first()
    await expect(demoButton).toBeVisible()
    await demoButton.click()

    // 3. Verify redirected to Documents dashboard
    await expect(page).toHaveURL(/.*\/documents/)
    await expect(page.locator('text=Documents')).toBeVisible()

    // 4. Upload a sample PDF
    const samplePdfPath = path.resolve(__dirname, '../../samples/rag_architecture_guide.pdf')
    const fileChooserPromise = page.waitForEvent('filechooser').catch(() => null)
    
    // Set file input if direct input exists or trigger file chooser
    const fileInput = page.locator('input[type="file"]')
    if (await fileInput.count() > 0) {
      await fileInput.setInputFiles(samplePdfPath)
    } else {
      const dropzone = page.locator('text=Click or drag PDF here')
      await dropzone.click()
      const fileChooser = await fileChooserPromise
      if (fileChooser) {
        await fileChooser.setFiles(samplePdfPath)
      }
    }

    // 5. Wait for the upload job to complete
    // Either document card transitions to 'completed' or badge appears
    await expect(page.locator('text=completed, text=Ready, [data-status="completed"]').first()).toBeVisible({ timeout: 45000 })

    // 6. Navigate to Chat interface for the document
    const chatLink = page.locator('a:has-text("Open Chat"), button:has-text("Chat"), a[href*="/chat/"]').first()
    await chatLink.click()
    await expect(page).toHaveURL(/.*\/chat\/\d+/)

    // 7. Ask a question using a starter prompt or typing
    const starterPrompt = page.locator('button:has-text("How does Reciprocal Rank Fusion"), button:has-text("Summarise")').first()
    if (await starterPrompt.isVisible()) {
      await starterPrompt.click()
    } else {
      const input = page.locator('input[placeholder*="Ask a question"], textarea')
      await input.fill('How does Reciprocal Rank Fusion combine dense and sparse retrieval scores?')
      await page.keyboard.press('Enter')
    }

    // 8. Verify streamed answer receives tokens and clickable citation chip appears
    await expect(page.locator('.citation-chip, button:has-text("[S1]"), span:has-text("[S1]")').first()).toBeVisible({ timeout: 30000 })

    // 9. Click citation chip to open Citation side panel
    const citationChip = page.locator('.citation-chip, button:has-text("[S1]"), span:has-text("[S1]")').first()
    await citationChip.click()
    await expect(page.locator('text=Source Citation, text=Citation Details')).toBeVisible()

    // 10. Open Retrieval Inspector
    const inspectorToggle = page.locator('button:has-text("Retrieval Inspector")').first()
    await expect(inspectorToggle).toBeVisible()
    await inspectorToggle.click()

    // Verify inspector reveals diagnostics (candidates, latency, or query type)
    await expect(page.locator('text=Candidates, text=Rerank, text=Latency, text=Query Type').first()).toBeVisible()
  })
})
