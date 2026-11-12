export default defineAppConfig({
  ui: {
    card: {
      slots: {
        root: 'min-w-0',
      },
    },
    table: {
      slots: {
        root: 'max-w-full',
      },
    },
    formField: {
      slots: {
        root: 'min-w-0',
        labelWrapper: 'flex-wrap',
        label: '[overflow-wrap:anywhere]',
        description: '[overflow-wrap:anywhere]',
      },
    },
    colors: {
      primary: 'sky',
      neutral: 'zinc',
    },
  },
})
