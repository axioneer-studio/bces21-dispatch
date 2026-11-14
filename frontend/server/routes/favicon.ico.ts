import { sendRedirect } from 'h3'

export default defineEventHandler((event) => {
  return sendRedirect(event, 'https://s3.axioneer.com/bces21-dispatch/images/favicon.png', 301)
})