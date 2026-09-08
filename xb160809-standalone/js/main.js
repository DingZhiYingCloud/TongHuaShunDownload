var index = 0,
  imgnum = $('.imgList li').length,
  width = 0,
  isie6 = !1
$(function () {
  // 注: 原站会在加载后把 .a9 的 href/title 写回外站(QQ群), 与本站"外链全部替换为友情链接"策略冲突, 已移除
  TA.log({
    id: 'Hevo_58fd9a98_592',
    fid: 'info_gather',
    sid: 'ad_market_2018031201'
  })
  width = 1200 > document.documentElement.clientWidth ? 1200 : document.documentElement.clientWidth
  $('.img3').width(width)
  $('.popup').width(width)
  $('.imgList').find('div').width(width)
  $('.img1_1, .img1_2, .img1_3, .img2_1, .img2_2, .img4_1, .img4_2, .img4_3, .img5_1, .img5_2').width(width)
  $('.indexList').css('left', width / 2 - 77 + 'px')
  $('.indexList').find('li').eq(0).css('background-position', '0 0')
  var a = !!window.ActiveXObject,
    b = a && !window.XMLHttpRequest
  a && b && (isie6 = !0)
})
$('.a5').click(function () {
  TA.log({
    id: 'Hevo_58d230df_409'
  })
})
$('.a6').click(function () {
  TA.log({
    id: 'Hevo_58d230ab_64'
  })
})
$('.a3').click(function () {
  TA.log({
    id: 'Hevo_58d23047_546'
  })
})
$('.a9').click(function () {
  TA.log({
    id: 'Hevo_58d2318e_995'
  })
})
$('.a8').click(function () {
  TA.log({
    id: 'Hevo_5994097c_320'
  })
})
$('.a7').click(function () {
  TA.log({
    id: 'Hevo_599409bb_262'
  })
})
$('#closeBtn').click(function () {
  $('#closeBox').hide()
})
var autoChange = setInterval(function () {
  index < imgnum && (index == imgnum - 1 && ($('.imgList').css('left', 0), (index = 0)), index++, changeTo(index))
}, 5e3)
$('.indexList')
  .find('li')
  .each(function (a) {
    $(this).click(function () {
      clearInterval(autoChange)
      changeTo(a)
      index = a
      autoChangeAgain()
    })
  })
function autoChangeAgain() {
  autoChange = setInterval(function () {
    index < imgnum &&
      (index == imgnum - 1
        ? ($('.imgList').animate(
            {
              left: '0'
            },
            1e3
          ),
          (index = 0))
        : index++,
      changeTo(index))
  }, 5e3)
}
function changeTo(a) {
  var b = a * width
  $('.imgList').animate(
    {
      left: '-' + b + 'px'
    },
    1e3
  )
  $('.indexList').find('li').css('background-position', '0 -20px')
  $('.indexList')
    .find('li')
    .eq(a % 5)
    .css('background-position', '0 0')
}
window.onresize = function () {
  width = 1200 > document.documentElement.clientWidth ? 1200 : document.documentElement.clientWidth
  $('.img3').width(width)
  $('.popup').width(width)
  $('.imgList').find('div').width(width)
  $('.img1_1, .img1_2, .img1_3, .img2_1, .img2_2, .img4_1, .img4_2, .img4_3, .img5_1, .img5_2').width(width)
  $('.indexList').css('left', width / 2 - 77 + 'px')
}
window.onscroll = function () {
  0 < $(document).scrollTop() ? $('.popup').addClass('popup_fixed') : $('.popup').removeClass('popup_fixed')
  isie6 || $('.popup').css('left', -$(window).scrollLeft() + 'px')
}
